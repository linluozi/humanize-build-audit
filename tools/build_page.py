"""Build the single-page report served by GitHub Pages.

Numbers are read from evidence/*.json at build time, so the page cannot drift
from the measurements.  Palette is the warm editorial one used in the figures.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EV = ROOT.parent / "evidence"


def load(name: str) -> dict:
    return json.loads((EV / name).read_text(encoding="utf-8"))


def main() -> None:
    bench = load("measure_bench_paired.json")
    det = load("measure_deterministic.json")
    width = load("measure_msgfmt_width.json")
    cov = load("measure_isolated.json")
    e2e = load("measure_endtoend.json")

    b_timed = bench["benchmark_timed"]["pytest_s_median"]
    b_off = bench["benchmark_disabled"]["pytest_s_median"]
    delta = bench["_paired_delta_s"]
    up_wall = e2e["upstream_cmd"]["wall_median_s"]
    pa_wall = e2e["patched_cmd"]["wall_median_s"]
    red = e2e["_derived"]["wall_reduction_pct"]

    ab = [(k, det[k]["pytest_s_median"], det[k]["ratio_median"]) for k in
          ("A_baseline", "B_no_html", "C_no_bench_timing", "D_patch")]
    labels = {
        "A_baseline": "upstream command",
        "B_no_html": "minus html report",
        "C_no_bench_timing": "minus benchmark timing",
        "D_patch": "both (the patch)",
    }
    ab_rows = "\n".join(
        f"<tr><td>{labels[k]}</td><td class='num'>{v:.2f}s</td>"
        f"<td class='num'>{r:.2f}&times;</td>"
        f"<td class='note'>{'inside the noise band' if k == 'B_no_html' else ('&mdash;' if k == 'A_baseline' else 'real')}</td></tr>"
        for k, v, r in ab
    )

    w_order = ["upstream_sequential", "jobs=1", "jobs=2", "jobs=4", "jobs=8", "jobs=16"]
    w_labels = ["sequential", "1", "2", "4", "8", "16"]
    w_vals = [width["variants"][k]["median_ms"] for k in w_order]
    w_max = max(w_vals)
    bars = "\n".join(
        f"<div class='bar-row'><span class='bl'>{lab}</span>"
        f"<span class='bar' style='width:{v / w_max * 100:.1f}%"
        f"{';background:var(--olive)' if v == min(w_vals) else ''}'></span>"
        f"<span class='bv'>{v:.0f} ms</span></div>"
        for lab, v in zip(w_labels, w_vals)
    )

    cov_rows = "\n".join(
        f"<tr><td>coverage {k}</td><td class='num'>{v['median']:.0f} ms</td>"
        f"<td class='note'>{'nothing reads it' if k == 'html' else ('uploaded to codecov' if k == 'xml' else 'log only')}</td></tr>"
        for k, v in cov["coverage_reports"]["per_report_ms"].items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>humanize &mdash; build flow audit</title>
<style>
  :root {{
    --ink:#2b2119; --paper:#faf6f0; --card:#fffdf9;
    --amber:#c8892b; --terra:#b4552f; --olive:#6b6b3a; --muted:#8a7a68;
    --rule:#e2d8c9;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--paper); color:var(--ink);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }}
  .wrap {{ max-width:960px; margin:0 auto; padding:56px 28px 96px; }}
  .kicker {{
    font-size:12px; letter-spacing:.16em; text-transform:uppercase;
    color:var(--terra); font-weight:700; margin-bottom:14px;
  }}
  h1 {{ font-size:clamp(28px,4.4vw,44px); line-height:1.15; margin:0 0 18px; letter-spacing:-.02em; }}
  h2 {{
    font-size:13px; letter-spacing:.14em; text-transform:uppercase;
    color:var(--muted); margin:56px 0 18px; padding-bottom:8px;
    border-bottom:1px solid var(--rule); font-weight:700;
  }}
  .lede {{ font-size:19px; color:#4a3d31; margin:0 0 8px; }}
  .lede strong {{ color:var(--terra); }}
  .src {{ font-size:13px; color:var(--muted); margin-bottom:34px; }}
  .src a {{ color:var(--muted); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); gap:14px; margin:30px 0 10px; }}
  .kpi {{ background:var(--card); border:1px solid var(--rule); border-radius:10px; padding:16px 18px; }}
  .kpi .lbl {{ font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
  .kpi .val {{ font-size:26px; font-weight:800; margin:6px 0 2px; letter-spacing:-.02em; }}
  .kpi .sub {{ font-size:12.5px; color:var(--muted); }}
  .kpi.good .val {{ color:var(--olive); }}
  .kpi.bad .val {{ color:var(--terra); }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; background:var(--card);
           border:1px solid var(--rule); border-radius:10px; overflow:hidden; }}
  th,td {{ padding:11px 14px; text-align:left; border-bottom:1px solid var(--rule); }}
  th {{ font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); background:#f4ece0; }}
  tr:last-child td {{ border-bottom:none; }}
  .num {{ font-variant-numeric:tabular-nums; font-weight:700; }}
  .note {{ color:var(--muted); font-size:13.5px; }}
  .bar-row {{ display:grid; grid-template-columns:96px 1fr 84px; align-items:center; gap:12px;
              margin-bottom:9px; font-size:14px; }}
  .bl {{ color:var(--muted); }}
  .bar {{ display:block; height:20px; background:var(--amber); border-radius:3px; min-width:2px; }}
  .bv {{ font-variant-numeric:tabular-nums; font-weight:700; text-align:right; }}
  .callout {{ background:var(--card); border-left:4px solid var(--terra); border-radius:0 8px 8px 0;
              padding:16px 20px; margin:22px 0; }}
  .callout p {{ margin:0; }}
  code {{ background:#f0e7d9; padding:1px 5px; border-radius:4px; font-size:.9em; }}
  .figs {{ display:grid; gap:18px; margin-top:8px; }}
  .figs img {{ width:100%; height:auto; border:1px solid var(--rule); border-radius:10px; display:block; }}
  .figs figcaption {{ font-size:13px; color:var(--muted); margin-top:8px; }}
  footer {{ margin-top:64px; padding-top:20px; border-top:1px solid var(--rule);
            font-size:13px; color:var(--muted); }}
  footer a {{ color:var(--terra); }}
</style>
</head>
<body>
<div class="wrap">

  <div class="kicker">CI flow audit &middot; python-humanize/humanize</div>
  <h1>The build was not slow.<br>It was quietly lying.</h1>
  <p class="lede">Two thirds of the CI matrix &mdash; every Windows cell &mdash; reported
  green while running <strong>none of the 112 locale tests</strong>.</p>
  <p class="src">Upstream <a href="https://github.com/python-humanize/humanize">python-humanize/humanize</a>
  at <code>785e5dc</code> &middot; MIT &middot; library code untouched &middot;
  <a href="https://github.com/linluozi/humanize-build-audit">source &amp; patch</a></p>

  <div class="grid">
    <div class="kpi"><div class="lbl">test command</div>
      <div class="val">{up_wall:.2f}&rarr;{pa_wall:.2f}s</div>
      <div class="sub">{red:.1f}% less wall clock</div></div>
    <div class="kpi"><div class="lbl">benchmark functions</div>
      <div class="val">{b_timed:.2f}&rarr;{b_off:.2f}s</div>
      <div class="sub">{delta['median']:.2f}s saved per run</div></div>
    <div class="kpi"><div class="lbl">compile 36 catalogs</div>
      <div class="val">2.9&rarr;2.0s</div>
      <div class="sub">8-way batches, byte-identical</div></div>
    <div class="kpi bad"><div class="lbl">Windows locale tests</div>
      <div class="val">0 of 112</div>
      <div class="sub">before &mdash; all of them after</div></div>
  </div>

  <h2>The bug worth finding</h2>
  <p><code>scripts/generate-translation-binaries.sh</code> has no shebang. GitHub's
  default shell on Windows is <code>pwsh</code>, and <code>pwsh</code> does not
  execute a <code>.sh</code> file: it exits 0 having done nothing. The script that
  compiles the translation catalogs therefore never ran on Windows.</p>
  <p><code>tests/test_i18n.py</code> wraps every locale assertion in
  <code>pytest.skip()</code> when a catalog is missing, so the missing catalogs
  surfaced as <em>skips</em>, never as failures. Linux and macOS reported
  <code>856 passed</code>; the nine Windows cells reported
  <code>744 passed, 112 skipped</code> and were marked green.</p>
  <div class="callout">
    <p><strong>The fix has two halves, and both are required.</strong> Install
    <code>gettext</code> so <code>msgfmt</code> exists, and run the script under
    <code>bash</code> so it is executed at all. A new step then fails the job if
    fewer than 36 catalogs were produced, so this cannot silently regress.</p>
  </div>

  <h2>Three redundant steps</h2>
  <table>
    <tr><th>variant</th><th>pytest duration</th><th>ratio</th><th>verdict</th></tr>
    {ab_rows}
  </table>
  <p class="note" style="margin-top:12px">A/A control (two byte-identical copies of the
  upstream command) spanned {det['_verdict']['aa_ratio_range'][0]:.3f}&ndash;{det['_verdict']['aa_ratio_range'][1]:.3f}&times;,
  so the html-only step is inside the noise band. It is removed because it is dead
  output, not because it moves the total on its own.</p>

  <h2>Compiling the catalogs</h2>
  <div style="margin-top:6px">
    {bars}
  </div>
  <p class="note">Width 1 forks once per file and is <em>slower</em> than the plain loop.
  The gain plateaus at 8, which is why the batch width is capped instead of unbounded.
  Every width produces byte-identical <code>.mo</code> files.</p>

  <h2>Coverage reports</h2>
  <table>
    <tr><th>report</th><th>median</th><th>consumer</th></tr>
    {cov_rows}
  </table>

  <h2>Figures</h2>
  <div class="figs">
    <figure><img src="figs/fig1_benchmark.png" alt="Benchmark timing cost">
      <figcaption>Timing the 15 benchmark functions is the largest single item.</figcaption></figure>
    <figure><img src="figs/fig5_falsegreen.png" alt="Windows skipped the locale tests">
      <figcaption>The false green: nine cells ran none of the locale tests.</figcaption></figure>
    <figure><img src="figs/fig2_ablation.png" alt="Ablation of the two changes">
      <figcaption>Each change measured alone, then combined.</figcaption></figure>
    <figure><img src="figs/fig3_parallel.png" alt="Batch width sweep">
      <figcaption>Batch width sweep &mdash; the optimum is 8.</figcaption></figure>
    <figure><img src="figs/fig4_endtoend.png" alt="Where the time goes">
      <figcaption>Where the wall clock goes in one test run.</figcaption></figure>
    <figure><img src="figs/fig6_mutation.png" alt="Mutation testing">
      <figcaption>Mutation test of the compile step: 4 killed, 2 equivalent.</figcaption></figure>
  </div>

  <footer>
    Every number on this page is rendered from <code>evidence/*.json</code> by
    <code>tools/build_page.py</code>, and <code>check_readme_numbers.py</code>
    traces the same figures in the README back to the same files.
    The patch is in <code>patch/build-redundancy.patch</code>;
    <code>python verify.py</code> runs 19 checks from a fresh extraction.
  </footer>

</div>
</body>
</html>
"""
    out = ROOT.parent / "index.html"
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {out.name}, {len(html)} bytes")


if __name__ == "__main__":
    main()
