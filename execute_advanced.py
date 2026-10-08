"""Validate or sequentially execute a versioned JSON campaign, with safe resume."""
import argparse
import csv
import hashlib
import json
import math
import re
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULTS = dict(element=285, tip_size=0.0025, global_size=None, pressure=10000.0,
                ex=1e7, nu=0.27, load_points=10, linear=False)


def safe_label(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", value):
        raise ValueError(f"Invalid plan label: {value!r}")
    return value


def validate_plan(plan):
    if not isinstance(plan, dict) or not plan:
        raise ValueError("Plan must map groups to nonempty case lists")
    validated = {}
    for group, cases in plan.items():
        safe_label(group)
        if not isinstance(cases, list) or not cases:
            raise ValueError(f"Empty or invalid group: {group}")
        labels, result = set(), []
        for case in cases:
            if not isinstance(case, dict) or "case" not in case:
                raise ValueError("Each case needs a case label")
            unknown = set(case) - {"case", *DEFAULTS}
            if unknown:
                raise ValueError(f"Unknown case keys: {sorted(unknown)}")
            label = safe_label(case["case"])
            if label in labels:
                raise ValueError(f"Duplicate case in {group}: {label}")
            labels.add(label)
            value = {**DEFAULTS, **case}
            if type(value["element"]) is not int or value["element"] not in (285, 187):
                raise ValueError("element must be 285 or 187")
            for key in ("tip_size", "pressure", "ex", "nu", "global_size"):
                number = value[key]
                if key == "global_size" and number is None:
                    continue
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                    raise ValueError(f"{key} must be finite numeric data")
                if key == "nu":
                    if not -1 < number < 0.5:
                        raise ValueError("nu must be between -1 and 0.5")
                elif number <= 0:
                    raise ValueError(f"{key} must be positive")
            if type(value["load_points"]) is not int or value["load_points"] < 2:
                raise ValueError("load_points must be an integer >= 2")
            if type(value["linear"]) is not bool:
                raise ValueError("linear must be a Boolean")
            result.append(value)
        validated[group] = result
    return validated


def resolve_campaign(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    boundary = (ROOT / "results" / "campaigns").resolve()
    if path == boundary or not path.is_relative_to(boundary):
        raise ValueError("Campaign must be a subdirectory of results/campaigns in this repository")
    safe_label(path.name)
    if not path.name[0].isalpha():
        raise ValueError('Campaign name must start with a letter')
    return path


def completed_summary(record, expected):
    path = Path(record["run_directory"])
    path = ROOT / path if not path.is_absolute() else path
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    keys = dict(element=f"SOLID{expected['element']}", tip_size_in=expected["tip_size"],
                global_size_in=expected["global_size"], nominal_pressure_peak_psi=expected["pressure"],
                youngs_modulus_psi=expected["ex"], poissons_ratio=expected["nu"],
                pressure_table_points=expected["load_points"], nlgeom=not expected["linear"])
    if record.get("status") != "solved" or summary.get("converged") is not True:
        raise ValueError("Resume record is not verified solved")
    if summary.get('case') != record.get('case'):
        raise ValueError('Resume case identity differs')
    if any(summary.get(key) != value for key, value in keys.items()):
        raise ValueError("Resume inputs differ from stored results")
    for key in ("max_u_in", "max_s1_psi", "max_seqv_psi"):
        if not math.isfinite(summary[key]) or not math.isclose(float(record[key]), summary[key], rel_tol=1e-10):
            raise ValueError("Resume CSV disagrees with summary")
    if not (path / "baseline.vtu").is_file():
        raise ValueError("Resume mesh is missing")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", help="results/campaigns/<unique-name>")
    parser.add_argument("mode", choices=["plan"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--plan-only", action="store_true", help="No imports, solver or output writes")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    plan = validate_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    campaign = resolve_campaign(args.campaign)
    print(f"Validated {len(plan)} groups / {sum(map(len, plan.values()))} structural cases")
    if args.plan_only:
        print("PASS: dry validation; no MAPDL started")
        return
    campaign.mkdir(parents=True, exist_ok=True)
    fingerprints = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                    for name in ('data/geometry/LatheCutter.anf','src/baseline_advanced.py','src/mapdl_session.py')}
    identity = {"schema": 1, "no_plots": args.no_plots, "plan": plan, 'input_source_sha256': fingerprints}
    manifest = campaign / "execution_plan.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != identity:
        raise ValueError("Stored campaign plan differs; choose a new campaign name")
    manifest.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    from src.baseline_advanced import run
    for group, cases in plan.items():
        folder = campaign / group
        folder.mkdir(exist_ok=True)
        csv_path = folder / "study_results.csv"
        records = list(csv.DictReader(csv_path.open(encoding="utf-8-sig"))) if csv_path.exists() else []
        if len({r['case'] for r in records}) != len(records):
            raise ValueError("Duplicate resume records")
        expected_labels = {f"{campaign.name}_{group}_{c['case']}" for c in cases}
        if any(r['case'] not in expected_labels for r in records):
            raise ValueError("Unexpected resume case")
        for spec in cases:
            label = f"{campaign.name}_{group}_{spec['case']}"
            stored = next((r for r in records if r["case"] == label), None)
            if stored:
                completed_summary(stored, spec)
                print(f"Verified resume: {label}", flush=True)
                continue
            try:
                run_dir = run(args.no_plots, case=label, element=spec['element'],
                              tip_size=spec['tip_size'], global_size=spec['global_size'],
                              pressure_peak=spec['pressure'], ex=spec['ex'], nu=spec['nu'],
                              load_points=spec['load_points'], nlgeom=not spec['linear'])
                summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
                summary.update(status="solved", study=group, run_directory=run_dir.relative_to(ROOT).as_posix())
                records.append(summary)
                fields = sorted(set().union(*(r.keys() for r in records)))
                temporary = csv_path.with_suffix(".tmp")
                with temporary.open("w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(records)
                temporary.replace(csv_path)
            except Exception:
                failures = campaign / "failures"
                failures.mkdir(exist_ok=True)
                from datetime import datetime
                target = failures / f"{label}_{datetime.now():%Y%m%d_%H%M%S_%f}.txt"
                target.write_text(traceback.format_exc(), encoding="utf-8")
                raise
    print(f"Completed campaign: {campaign}")


if __name__ == "__main__":
    main()
