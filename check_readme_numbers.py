"""Cross-check every number in README.md against evidence/*.json.

The report is only worth reading if its numbers can be traced back to a
measurement.  This script extracts the figures that appear in the prose and
tables, recomputes them from the JSON, and fails loudly on a mismatch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EV = ROOT / "evidence"
README = ROOT / "README.md"


def load(name: str) -> dict:
    return json.loads((EV / name).read_text(encoding="utf-8"))


def main() -> int:
    text = README.read_text(encoding="utf-8")
    bench = load("measure_bench_paired.json")
    det = load("measure_deterministic.json")
    iso = load("measure_isolated.json")
    width = load("measure_msgfmt_width.json")
    e2e = load("measure_endtoend.json")
    cov = load("evidence_coverage_equivalence.json")

    checks: list[tuple[str, bool, str]] = []

    def expect(label: str, value: str, should_exist: bool = True) -> None:
        found = value in text
        checks.append((label, found == should_exist,
                       f"{value!r} {'found' if found else 'missing'}"))

    # section 0 / 1
    expect("bench timed median", f"{bench['benchmark_timed']['pytest_s_median']:.2f} s")
    expect("bench disabled median", f"{bench['benchmark_disabled']['pytest_s_median']:.2f} s")
    expect("bench paired median",
           f"{bench['_paired_delta_s']['median']:.2f} s")
    expect("bench paired range",
           f"{bench['_paired_delta_s']['min']:.2f}–{bench['_paired_delta_s']['max']:.2f}")

    # coverage report timings
    for key in ("term", "xml", "html"):
        ms = iso["coverage_reports"]["per_report_ms"][key]["median"]
        expect(f"coverage {key} median", f"{ms:.0f} ms")

    # ablation table
    for key in ("A_baseline", "B_no_html", "C_no_bench_timing", "D_patch"):
        v = det[key]
        expect(f"{key} median", f"{v['pytest_s_median']:.2f} s")
        if key != "A_baseline":
            expect(f"{key} ratio", f"{v['ratio_median']:.2f}×")

    # A/A band
    lo, hi = det["_verdict"]["aa_ratio_range"]
    expect("A/A band", f"{lo:.3f}–{hi:.3f}")

    # parallel sweep
    for name, v in width["variants"].items():
        expect(f"{name} median", f"{v['median_ms']:.0f} ms")

    # end to end
    expect("e2e upstream wall", f"{e2e['upstream_cmd']['wall_median_s']:.2f} s")
    expect("e2e patched wall", f"{e2e['patched_cmd']['wall_median_s']:.2f} s")
    expect("e2e reduction", f"{e2e['_derived']['wall_reduction_pct']:.1f} %")

    # coverage equivalence claim
    checks.append((
        "coverage equivalence claim",
        cov["normalized_bytes_equal"] and cov["per_line_difference_count"] == 0,
        f"normalized_equal={cov['normalized_bytes_equal']}, "
        f"line_diffs={cov['per_line_difference_count']}",
    ))
    expect("coverage totals", f"{cov['totals']['lines_valid']} valid lines")
    expect("coverage covered", f"{cov['totals']['lines_covered']} covered")

    # byte-identity claim for the parallel compile
    checks.append((
        "parallel compile byte-identical",
        width["all_widths_byte_identical"] is True,
        str(width["all_widths_byte_identical"]),
    ))

    failed = [c for c in checks if not c[1]]
    for label, ok, detail in checks:
        print(f"[{'OK  ' if ok else 'FAIL'}] {label:34s} {detail}")
    print(f"\n{len(checks) - len(failed)}/{len(checks)} README numbers traced to evidence")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
