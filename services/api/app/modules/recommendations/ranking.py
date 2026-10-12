"""LOCKED v3 weights; continuous coverage is a documented temporary MVP policy."""
from decimal import Decimal
from math import isfinite

ALGORITHM_VERSION = "v3-mvp-coverage-fsp-demo-2"
WEIGHTS = {"skillFit": 0.50, "assessmentStrength": 0.35, "fspBonus": 0.15}


def normalized(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 100:
        raise ValueError("Invalid certified evidence")
    return Decimal(str(value)) / 100


def calculate(required, optional, evidence, technical_score, confirmed_fsp=False, *, fsp_bonus=None):
    """No I/O or eligibility inference. Missing evidence=0, empty required=0.

    fsp_bonus is a synthetic-demo registry score, never inferred from DB seed rows.
    """
    def coverage(skills):
        return sum((normalized(evidence.get(s, 0)) for s in skills), Decimal(0)) / len(skills) if skills else Decimal(0)

    required_coverage, optional_coverage = coverage(required), coverage(optional)
    skill = (Decimal("0.8") * required_coverage + Decimal("0.2") * optional_coverage
             if optional else required_coverage)
    strength = normalized(technical_score)
    if fsp_bonus is not None:
        if confirmed_fsp or isinstance(fsp_bonus, bool) or not isinstance(fsp_bonus, (int, float)) or not isfinite(fsp_bonus) or not 0 <= fsp_bonus <= 1:
            raise ValueError("Invalid FSP bonus")
        bonus = Decimal(str(fsp_bonus))
    else:
        bonus = Decimal(1 if confirmed_fsp else 0)
    score = Decimal("0.50") * skill + Decimal("0.35") * strength + Decimal("0.15") * bonus
    components = {"skillFit": float(skill), "assessmentStrength": float(strength), "fspBonus": float(bonus)}
    reasons = (f"Required skill evidence: {required_coverage * 100:.1f}%",
               f"Technical test: {strength * 100:.1f}%",
               f"FSP bonus: {bonus * 100:.1f}%")
    return float(score), components, reasons
