"""Deterministic multiplicative candidate pre-filter.

The module broadens retrieval to adjacent roles/grades/technology stacks while
keeping hard privacy and verification gates.  It does not read a database and
it does not calculate the locked v3 quality ranking score.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import json

D = Decimal
ONE = D("1")
ZERO = D("0")


@dataclass(frozen=True)
class SkillRequirement:
    skill_id: str
    priority: int = 3
    required: bool = True


@dataclass(frozen=True)
class AchievementRequirement:
    tag: str
    priority: int = 3
    required: bool = False


@dataclass(frozen=True)
class FilterNeed:
    role_id: str
    grade_id: str
    min_experience_years: Decimal | None = None
    max_experience_years: Decimal | None = None
    skills: tuple[SkillRequirement, ...] = ()
    achievements: tuple[AchievementRequirement, ...] = ()
    salary_budget_max: Decimal | None = None
    work_format: str | None = None
    location: str | None = None
    hard_skill_ids: frozenset[str] = frozenset()
    hard_salary_cap: bool = False


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    role_ids: tuple[str, ...]
    grade_id: str
    experience_years: Decimal | None = None
    skill_ids: tuple[str, ...] = ()
    verified_achievement_tags: tuple[str, ...] = ()
    salary_expectation: Decimal | None = None
    work_formats: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    verified_email: bool = True
    publication_consent: bool = True
    submitted_category_attempt: bool = True


@dataclass(frozen=True)
class Factor:
    code: str
    coefficient: Decimal
    reason: str


@dataclass(frozen=True)
class FilteredCandidate:
    candidate_id: str
    filter_fit: Decimal
    factors: tuple[Factor, ...]


@dataclass(frozen=True)
class ExcludedCandidate:
    candidate_id: str
    reason: str


@dataclass(frozen=True)
class FilterResult:
    selected: tuple[FilteredCandidate, ...]
    excluded: tuple[ExcludedCandidate, ...]


class FilterInputError(ValueError):
    pass


@dataclass(frozen=True)
class Taxonomy:
    role_edges: Mapping[str, Mapping[str, Decimal]]
    grade_fit: Mapping[str, Mapping[str, Decimal]]
    role_aliases: Mapping[str, str]
    grade_aliases: Mapping[str, str]
    skill_aliases: Mapping[str, str]
    skill_edges: Mapping[str, Mapping[str, Decimal]]
    known_skills: frozenset[str]


@dataclass(frozen=True)
class FilterPolicy:
    minimum_fit: Decimal
    maximum_role_hops: int
    unknown: Mapping[str, Decimal]
    experience_min_bands: tuple[tuple[Decimal, Decimal], ...]
    experience_max_bands: tuple[tuple[Decimal, Decimal], ...]
    stack_required_missing: Decimal
    stack_optional_missing: Decimal
    stack_optional_weight: Decimal
    achievement_required_missing: Decimal
    achievement_optional_missing: Decimal
    achievement_optional_weight: Decimal
    salary_bands: tuple[tuple[Decimal, Decimal], ...]
    format_matrix: Mapping[str, Mapping[str, Decimal]]
    location_different: Decimal
    precision: Decimal


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _coefficient(value, *, allow_zero=False) -> Decimal:
    try:
        number = D(str(value))
    except Exception as exc:
        raise FilterInputError("invalid taxonomy coefficient") from exc
    if not number.is_finite() or not (ZERO <= number <= ONE if allow_zero else ZERO < number <= ONE):
        raise FilterInputError("taxonomy coefficient outside allowed range")
    return number


def _aliases(entries, *, label=None):
    aliases = {}
    for item in entries:
        for alias in (item["id"], *((item[label],) if label else ()), *item["aliases"]):
            key = alias.casefold()
            if not key or key in aliases and aliases[key] != item["id"]:
                raise FilterInputError("ambiguous taxonomy alias")
            aliases[key] = item["id"]
    return aliases


def _validate_configs(roles, grades, skills, policy, sources):
    if any(d.get("schema_version") != 1 for d in (roles, grades, skills, policy, sources)):
        raise FilterInputError("incompatible taxonomy schema")
    version = roles.get("catalog_version")
    if not version or any(d.get("catalog_version") != version for d in (grades, skills, sources)):
        raise FilterInputError("taxonomy versions differ")
    if policy.get("policy_version") != "formal-filter-v1" or version != "talent-taxonomy-v1":
        raise FilterInputError("unsupported taxonomy policy version")
    source_ids = set(sources["sources"])
    for document in (roles, grades, skills):
        if not set(document["sources"]) <= source_ids:
            raise FilterInputError("unknown taxonomy source")
    def unique(items, label):
        ids = [item["id"] for item in items]
        if not ids or len(ids) != len(set(ids)):
            raise FilterInputError(f"duplicate or empty {label} IDs")
        return set(ids)
    role_ids = unique(roles["roles"], "role")
    grade_ids = unique(grades["grades"], "grade")
    skill_ids = unique(skills["skills"], "skill")
    _aliases(roles["roles"])
    _aliases(grades["grades"])
    for role in roles["roles"]:
        if not set(role.get("sources", roles["sources"])) <= source_ids:
            raise FilterInputError("unknown role source")
        related = [edge["role_id"] for edge in role["related_roles"]]
        if len(related) != len(set(related)) or any(target not in role_ids or target == role["id"] for target in related):
            raise FilterInputError("invalid related role")
        for edge in role["related_roles"]:
            _coefficient(edge["coefficient"])
    matrix = grades["candidate_to_requested_fit"]
    if set(matrix) != grade_ids or any(set(row) != grade_ids for row in matrix.values()):
        raise FilterInputError("incomplete grade matrix")
    for grade, row in matrix.items():
        if _coefficient(row[grade]) != ONE:
            raise FilterInputError("grade diagonal must equal one")
        for value in row.values():
            _coefficient(value, allow_zero=True)
    aliases = {}
    for skill in skills["skills"]:
        if not set(skill["role_ids"]) <= role_ids or not set(skill["sources"]) <= source_ids:
            raise FilterInputError("unknown skill role or source")
        for alias in (skill["id"], skill["label"], *skill["aliases"]):
            key = alias.casefold()
            if not key or key in aliases and aliases[key] != skill["id"]:
                raise FilterInputError("ambiguous skill alias")
            aliases[key] = skill["id"]
    pairs = set()
    for edge in skills["relations"]:
        a, b = edge["a"], edge["b"]
        if a not in skill_ids or b not in skill_ids or a == b or (a, b) in pairs:
            raise FilterInputError("invalid skill relation")
        pairs.add((a, b))
        _coefficient(edge["coefficient"])
    _coefficient(policy["minimum_filter_fit"])
    if type(policy["maximum_role_hops"]) is not int or not 1 <= policy["maximum_role_hops"] <= 2:
        raise FilterInputError("invalid role hop limit")
    precision = D(str(policy["coefficient_precision"]))
    if not precision.is_finite() or not ZERO < precision <= ONE:
        raise FilterInputError("invalid coefficient precision")
    for value in policy["unknown_values"].values():
        _coefficient(value)
    for section, keys in ((policy["stack"], ("required_missing", "optional_missing", "optional_weight_multiplier")),
                          (policy["achievements"], ("required_missing", "optional_missing", "optional_weight_multiplier"))):
        for key in keys:
            _coefficient(section[key])
    _coefficient(policy["location"]["different"])
    for row in policy["work_format"]["matrix"].values():
        for value in row.values():
            _coefficient(value)
    for bands, key in ((policy["experience"]["minimum_deficit_bands"], "max_years"),
                       (policy["experience"]["maximum_excess_bands"], "max_years"),
                       (policy["salary"]["over_budget_bands"], "max_ratio")):
        limits = [D(str(item[key])) for item in bands]
        if not limits or any(not n.is_finite() or n <= ZERO for n in limits) or limits != sorted(set(limits)):
            raise FilterInputError("invalid policy bands")
        for item in bands:
            _coefficient(item["coefficient"])


def load_runtime(config_dir: str | Path | None = None) -> tuple[Taxonomy, FilterPolicy]:
    root = Path(config_dir) if config_dir else Path(__file__).with_name("config")
    roles = _load_json(root / "roles.v1.json")
    grades = _load_json(root / "grades.v1.json")
    skills = _load_json(root / "skills.v1.json")
    policy = _load_json(root / "filtering-policy.v1.json")
    sources = _load_json(root / "sources.v1.json")
    try:
        _validate_configs(roles, grades, skills, policy, sources)
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise FilterInputError("invalid taxonomy configuration") from exc

    role_edges: dict[str, dict[str, Decimal]] = {}
    for role in roles["roles"]:
        role_edges[role["id"]] = {
            item["role_id"]: D(str(item["coefficient"]))
            for item in role["related_roles"]
        }

    known_skills = frozenset(item["id"] for item in skills["skills"])
    aliases: dict[str, str] = {}
    for item in skills["skills"]:
        aliases[item["id"].casefold()] = item["id"]
        aliases[item["label"].casefold()] = item["id"]
        for alias in item["aliases"]:
            aliases[alias.casefold()] = item["id"]
    skill_edges: dict[str, dict[str, Decimal]] = {skill: {} for skill in known_skills}
    for relation in skills["relations"]:
        a, b = relation["a"], relation["b"]
        coefficient = D(str(relation["coefficient"]))
        skill_edges[a][b] = coefficient
        if relation.get("symmetric", False):
            skill_edges[b][a] = coefficient

    def bands(value: Sequence[dict], limit_key: str) -> tuple[tuple[Decimal, Decimal], ...]:
        return tuple((D(str(item[limit_key])), D(str(item["coefficient"]))) for item in value)

    taxonomy = Taxonomy(
        role_edges=role_edges,
        grade_fit={candidate: {requested: D(str(value)) for requested, value in row.items()}
                   for candidate, row in grades["candidate_to_requested_fit"].items()},
        role_aliases=_aliases(roles["roles"]),
        grade_aliases=_aliases(grades["grades"]),
        skill_aliases=aliases,
        skill_edges=skill_edges,
        known_skills=known_skills,
    )
    filter_policy = FilterPolicy(
        minimum_fit=D(str(policy["minimum_filter_fit"])),
        maximum_role_hops=int(policy["maximum_role_hops"]),
        unknown={key: D(str(value)) for key, value in policy["unknown_values"].items()},
        experience_min_bands=bands(policy["experience"]["minimum_deficit_bands"], "max_years"),
        experience_max_bands=bands(policy["experience"]["maximum_excess_bands"], "max_years"),
        stack_required_missing=D(str(policy["stack"]["required_missing"])),
        stack_optional_missing=D(str(policy["stack"]["optional_missing"])),
        stack_optional_weight=D(str(policy["stack"]["optional_weight_multiplier"])),
        achievement_required_missing=D(str(policy["achievements"]["required_missing"])),
        achievement_optional_missing=D(str(policy["achievements"]["optional_missing"])),
        achievement_optional_weight=D(str(policy["achievements"]["optional_weight_multiplier"])),
        salary_bands=bands(policy["salary"]["over_budget_bands"], "max_ratio"),
        format_matrix={need: {candidate: D(str(value)) for candidate, value in row.items()}
                       for need, row in policy["work_format"]["matrix"].items()},
        location_different=D(str(policy["location"]["different"])),
        precision=D(str(policy["coefficient_precision"])),
    )
    return taxonomy, filter_policy


def _validate_need(need: FilterNeed, taxonomy: Taxonomy) -> None:
    if need.role_id not in taxonomy.role_edges:
        raise FilterInputError(f"unknown need.role_id: {need.role_id}")
    if need.grade_id not in taxonomy.grade_fit:
        raise FilterInputError(f"unknown need.grade_id: {need.grade_id}")
    seen: set[str] = set()
    for requirement in need.skills:
        if not 1 <= requirement.priority <= 5:
            raise FilterInputError(f"skill priority must be 1..5: {requirement.skill_id}")
        canonical = taxonomy.skill_aliases.get(requirement.skill_id.casefold())
        if canonical is None:
            raise FilterInputError(f"unknown need skill: {requirement.skill_id}")
        if canonical in seen:
            raise FilterInputError(f"duplicate need skill: {canonical}")
        seen.add(canonical)
    hard_skills: set[str] = set()
    for value in need.hard_skill_ids:
        canonical = taxonomy.skill_aliases.get(value.casefold())
        if canonical is None:
            raise FilterInputError(f"unknown hard skill: {value}")
        hard_skills.add(canonical)
    if not hard_skills <= seen:
        raise FilterInputError("hard_skill_ids must also occur in need.skills")
    for requirement in need.achievements:
        if not requirement.tag.strip():
            raise FilterInputError("achievement tag cannot be empty")
        if not 1 <= requirement.priority <= 5:
            raise FilterInputError(f"achievement priority must be 1..5: {requirement.tag}")
    if need.min_experience_years is not None and need.min_experience_years < ZERO:
        raise FilterInputError("min_experience_years must be non-negative")
    if need.max_experience_years is not None and need.max_experience_years < ZERO:
        raise FilterInputError("max_experience_years must be non-negative")
    if (need.min_experience_years is not None and need.max_experience_years is not None
            and need.min_experience_years > need.max_experience_years):
        raise FilterInputError("min_experience_years cannot exceed max_experience_years")
    if need.salary_budget_max is not None and need.salary_budget_max <= ZERO:
        raise FilterInputError("salary_budget_max must be positive")
    if need.work_format not in (None, "any", "remote", "hybrid", "office"):
        raise FilterInputError(f"unknown need.work_format: {need.work_format}")


def _best_graph_fit(start_ids: Iterable[str], target: str,
                    graph: Mapping[str, Mapping[str, Decimal]], max_hops: int) -> Decimal:
    starts = set(start_ids)
    if target in starts:
        return ONE
    frontier = {item: ONE for item in starts if item in graph}
    best = ZERO
    for _ in range(max_hops):
        next_frontier: dict[str, Decimal] = {}
        for node, path_fit in frontier.items():
            for neighbour, edge_fit in graph.get(node, {}).items():
                candidate_fit = path_fit * edge_fit
                if neighbour == target:
                    best = max(best, candidate_fit)
                if candidate_fit > next_frontier.get(neighbour, ZERO):
                    next_frontier[neighbour] = candidate_fit
        frontier = next_frontier
    return best


def _band(value: Decimal, bands: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    for upper, coefficient in bands:
        if value <= upper:
            return coefficient
    return bands[-1][1]


def _weighted_geometric(values: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    if not values:
        return ONE
    with localcontext() as context:
        context.prec = 28
        total_weight = sum((weight for _, weight in values), ZERO)
        if total_weight <= ZERO:
            raise FilterInputError("factor weights must be positive")
        # Configured coefficients are strictly positive; zero is reserved for hard exclusion.
        return (sum((weight * value.ln() for value, weight in values), ZERO) / total_weight).exp()


def _canonical_candidate_skills(candidate: Candidate, taxonomy: Taxonomy) -> frozenset[str]:
    return frozenset(
        canonical for value in candidate.skill_ids
        if (canonical := taxonomy.skill_aliases.get(value.casefold())) is not None
    )


def _stack_factor(need: FilterNeed, candidate: Candidate,
                  taxonomy: Taxonomy, policy: FilterPolicy) -> tuple[Decimal, str, bool]:
    if not need.skills:
        return ONE, "Стек не задан — фактор нейтрален", False
    candidate_skills = _canonical_candidate_skills(candidate, taxonomy)
    values: list[tuple[Decimal, Decimal]] = []
    notes: list[str] = []
    hard_miss = False
    hard_skills = {
        taxonomy.skill_aliases[value.casefold()]
        for value in need.hard_skill_ids
    }
    for requirement in need.skills:
        target = taxonomy.skill_aliases[requirement.skill_id.casefold()]
        fit = _best_graph_fit(candidate_skills, target, taxonomy.skill_edges, 1)
        if fit == ZERO:
            fit = policy.stack_required_missing if requirement.required else policy.stack_optional_missing
            notes.append(f"{target}:нет")
            if target in hard_skills:
                hard_miss = True
        elif fit == ONE:
            notes.append(f"{target}:точно")
        else:
            notes.append(f"{target}:близко={fit}")
        weight = D(requirement.priority)
        if not requirement.required:
            weight *= policy.stack_optional_weight
        values.append((fit, weight))
    return _weighted_geometric(values), "; ".join(notes), hard_miss


def _achievement_factor(need: FilterNeed, candidate: Candidate,
                        policy: FilterPolicy) -> tuple[Decimal, str]:
    if not need.achievements:
        return ONE, "Требования к достижениям не заданы — фактор нейтрален"
    have = {tag.casefold() for tag in candidate.verified_achievement_tags}
    values: list[tuple[Decimal, Decimal]] = []
    notes: list[str] = []
    for requirement in need.achievements:
        matched = requirement.tag.casefold() in have
        fit = ONE if matched else (policy.achievement_required_missing if requirement.required
                                   else policy.achievement_optional_missing)
        weight = D(requirement.priority)
        if not requirement.required:
            weight *= policy.achievement_optional_weight
        values.append((fit, weight))
        notes.append(f"{requirement.tag}:{'есть' if matched else 'нет'}")
    return _weighted_geometric(values), "; ".join(notes)


def _evaluate(need: FilterNeed, candidate: Candidate,
              taxonomy: Taxonomy, policy: FilterPolicy) -> FilteredCandidate | ExcludedCandidate:
    if not candidate.candidate_id:
        return ExcludedCandidate(candidate.candidate_id, "пустой candidate_id")
    for ok, reason in (
        (candidate.verified_email, "email не подтверждён"),
        (candidate.publication_consent, "нет согласия на публикацию"),
        (candidate.submitted_category_attempt, "нет завершённой категоризующей попытки"),
    ):
        if not ok:
            return ExcludedCandidate(candidate.candidate_id, reason)
    if candidate.grade_id not in taxonomy.grade_fit:
        return ExcludedCandidate(candidate.candidate_id, "неизвестный грейд")
    if not candidate.role_ids or any(role not in taxonomy.role_edges for role in candidate.role_ids):
        return ExcludedCandidate(candidate.candidate_id, "неизвестная или отсутствующая роль")
    if candidate.experience_years is not None and candidate.experience_years < ZERO:
        raise FilterInputError(f"candidate {candidate.candidate_id}: experience_years must be non-negative")
    if candidate.salary_expectation is not None and candidate.salary_expectation < ZERO:
        raise FilterInputError(f"candidate {candidate.candidate_id}: salary_expectation must be non-negative")

    factors: list[Factor] = []
    role = _best_graph_fit(candidate.role_ids, need.role_id, taxonomy.role_edges, policy.maximum_role_hops)
    if role == ZERO:
        return ExcludedCandidate(candidate.candidate_id, "роль дальше допустимого графа близости")
    factors.append(Factor("role", role, "точная роль" if role == ONE else "смежная роль"))

    grade = taxonomy.grade_fit[candidate.grade_id].get(need.grade_id, ZERO)
    if grade == ZERO:
        return ExcludedCandidate(candidate.candidate_id, "грейд вне допустимого расстояния")
    factors.append(Factor("grade", grade, "точный грейд" if grade == ONE else "соседний грейд"))

    experience = ONE
    experience_reason = "опыт соответствует"
    if need.min_experience_years is not None or need.max_experience_years is not None:
        if candidate.experience_years is None:
            experience = policy.unknown["experience"]
            experience_reason = "опыт не указан"
        elif need.min_experience_years is not None and candidate.experience_years < need.min_experience_years:
            experience = _band(need.min_experience_years - candidate.experience_years, policy.experience_min_bands)
            experience_reason = "опыт ниже минимума"
        elif need.max_experience_years is not None and candidate.experience_years > need.max_experience_years:
            experience = _band(candidate.experience_years - need.max_experience_years, policy.experience_max_bands)
            experience_reason = "опыт выше диапазона"
    factors.append(Factor("experience", experience, experience_reason))

    stack, stack_reason, hard_miss = _stack_factor(need, candidate, taxonomy, policy)
    if hard_miss:
        return ExcludedCandidate(candidate.candidate_id, "не выполнен hard must-have skill")
    factors.append(Factor("stack", stack, stack_reason))

    achievements, achievement_reason = _achievement_factor(need, candidate, policy)
    factors.append(Factor("achievements", achievements, achievement_reason))

    salary = ONE
    salary_reason = "зарплатные ожидания в бюджете"
    if need.salary_budget_max is not None:
        if candidate.salary_expectation is None:
            salary = policy.unknown["salary"]
            salary_reason = "зарплатные ожидания не указаны"
        elif candidate.salary_expectation > need.salary_budget_max:
            if need.hard_salary_cap:
                return ExcludedCandidate(candidate.candidate_id, "зарплатные ожидания выше жёсткого лимита")
            ratio = candidate.salary_expectation / need.salary_budget_max
            salary = _band(ratio, policy.salary_bands)
            salary_reason = f"ожидания выше бюджета: x{ratio.quantize(D('0.01'))}"
    factors.append(Factor("salary", salary, salary_reason))

    work_format = ONE
    format_reason = "формат работы соответствует"
    if need.work_format and need.work_format != "any":
        if not candidate.work_formats:
            work_format = policy.unknown["work_format"]
            format_reason = "формат работы не указан"
        else:
            row = policy.format_matrix.get(need.work_format)
            if row is None:
                raise FilterInputError(f"unknown need.work_format: {need.work_format}")
            work_format = max((row.get(value, policy.unknown["work_format"])
                               for value in candidate.work_formats), default=policy.unknown["work_format"])
            if work_format < ONE:
                format_reason = "предпочтительный формат отличается"
    factors.append(Factor("work_format", work_format, format_reason))

    location = ONE
    location_reason = "локация соответствует или не применима"
    if need.location and need.work_format != "remote":
        if not candidate.locations:
            location = policy.unknown["location"]
            location_reason = "локация не указана"
        elif need.location.casefold() not in {value.casefold() for value in candidate.locations}:
            location = policy.location_different
            location_reason = "другая локация"
    factors.append(Factor("location", location, location_reason))

    fit = ONE
    for factor in factors:
        fit *= factor.coefficient
    fit = fit.quantize(policy.precision)
    if fit < policy.minimum_fit:
        return ExcludedCandidate(candidate.candidate_id, f"filter_fit {fit} ниже порога {policy.minimum_fit}")
    return FilteredCandidate(candidate.candidate_id, fit, tuple(factors))


def filter_candidates(need: FilterNeed, candidates: Sequence[Candidate],
                      taxonomy: Taxonomy | None = None,
                      policy: FilterPolicy | None = None) -> FilterResult:
    """Return a deterministic broad cohort with a [0, 1] fit coefficient.

    Output is ordered by filter_fit DESC, then candidate_id ASC. The downstream
    ranker must still calculate verified quality and persist an immutable snapshot.
    """
    if taxonomy is None or policy is None:
        loaded_taxonomy, loaded_policy = load_runtime()
        taxonomy = taxonomy or loaded_taxonomy
        policy = policy or loaded_policy
    need = replace(need,
        role_id=taxonomy.role_aliases.get(need.role_id.casefold(), need.role_id),
        grade_id=taxonomy.grade_aliases.get(need.grade_id.casefold(), need.grade_id))
    _validate_need(need, taxonomy)
    seen: set[str] = set()
    selected: list[FilteredCandidate] = []
    excluded: list[ExcludedCandidate] = []
    for candidate in candidates:
        if candidate.candidate_id in seen:
            raise FilterInputError(f"duplicate candidate_id: {candidate.candidate_id}")
        seen.add(candidate.candidate_id)
        candidate = replace(candidate,
            role_ids=tuple(taxonomy.role_aliases.get(role.casefold(), role) for role in candidate.role_ids),
            grade_id=taxonomy.grade_aliases.get(candidate.grade_id.casefold(), candidate.grade_id))
        result = _evaluate(need, candidate, taxonomy, policy)
        (selected if isinstance(result, FilteredCandidate) else excluded).append(result)
    selected.sort(key=lambda item: (-item.filter_fit, item.candidate_id))
    excluded.sort(key=lambda item: item.candidate_id)
    return FilterResult(tuple(selected), tuple(excluded))
