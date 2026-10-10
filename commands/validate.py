"""Sequential MVP validation. BLOCKED is never success. No dev DB migrations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "infra/docker-compose.yml", "exec", "-T"]


def exit_code(rows):
    return 1 if any(r["status"] == "FAIL" for r in rows) else 2 if any(r["status"] == "BLOCKED" for r in rows) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-backend", action="store_true", help="Mark NOT_RUN/BLOCKED; never claim a cached PASS")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixtures")
    parser.add_argument("--labels")
    parser.add_argument("--ranking-command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    out = args.output or ROOT / ".cache" / "validation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    rows = []

    def blocked(name, reason):
        rows.append({"stage": name, "status": "BLOCKED", "reason": reason})
        print(f"{name}: BLOCKED — {reason}", flush=True)

    def run(name, command, timeout=1200, blocked_code=None):
        log = out / (name + ".log")
        try:
            with log.open("w", encoding="utf-8") as stream:
                proc = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                      timeout=timeout, encoding="utf-8")
            status = "PASS" if proc.returncode == 0 else ("BLOCKED" if proc.returncode == blocked_code else "FAIL")
            row = {"stage": name, "status": status, "exitCode": proc.returncode}
        except (OSError, subprocess.TimeoutExpired) as exc:
            row = {"stage": name, "status": "FAIL", "error": str(exc)}
        row.update(command=command, cwd=str(ROOT), log=str(log))
        rows.append(row)
        print(f"{name}: {row['status']} — {log}", flush=True)

    if args.skip_backend:
        blocked("backend-pytest", "NOT_RUN by request; previous results are documented separately")
    else:
        # Existing conftest creates fsp_test_<uuid>, migrates ONLY it, then drops it.
        run("backend-pytest", COMPOSE + ["api", "pytest", "-q"])
    package = json.loads((ROOT / "apps/web/package.json").read_text())
    # Build/lint in a temporary copy, never the live dev server's .next directory.
    setup = ('set -eu; work=$(mktemp -d /tmp/fsp-validation.XXXXXX); '
             'cp -R app package.json package-lock.json tsconfig.json next-env.d.ts '
             'next.config.js postcss.config.js tailwind.config.ts "$work/"; '
             'ln -s /app/node_modules "$work/node_modules"; cd "$work"; ')
    if "lint" in package["scripts"]:
        run("frontend-lint", COMPOSE + ["web", "sh", "-c", setup + "npm run lint"])
    else:
        blocked("frontend-lint", "No lint script or configured linter in apps/web")
    run("frontend-build", COMPOSE + ["web", "sh", "-c", setup + "NEXT_TELEMETRY_DISABLED=1 npm run build"])
    blocked("playwright-primary-flow", "No screens/config/spec or isolated E2E environment; ranking 503, content DEMO")
    evaluation = [sys.executable, str(ROOT / "commands/evaluate.py"), "--output", str(out / "evaluation.json")]
    for key in ("fixtures", "labels"):
        if getattr(args, key):
            evaluation += ["--" + key, getattr(args, key)]
    if args.ranking_command:
        evaluation += ["--ranking-command"] + args.ranking_command
    run("ds-ranking-evaluation", evaluation, blocked_code=2)
    run("assessment-synthetic-validation", [sys.executable, str(ROOT / "services/api/docs/v3/arch/validate_v3_skill_agents.py")])
    manifest = ROOT / "services/api/app/data/catalog/manifest.json"
    fingerprint = hashlib.sha256()
    for path in sorted((ROOT / "services/api").rglob("*")):
        if path.is_file() and not any(p in {"__pycache__", ".pytest_cache", ".venv"} for p in path.parts):
            fingerprint.update(path.relative_to(ROOT).as_posix().encode())
            fingerprint.update(path.read_bytes())
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "stages": rows,
              "exitCode": exit_code(rows),
              "backendTreeSha256": fingerprint.hexdigest(),
              "manifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {out / 'report.json'}")
    return exit_code(rows)


if __name__ == "__main__":
    raise SystemExit(main())
