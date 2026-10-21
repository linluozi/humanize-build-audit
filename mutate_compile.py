"""Mutation-test the translation compile step.

A green run proves nothing unless the checks can fail.  Each mutant breaks one
property the patched script is supposed to guarantee, and the harness records
whether the checks catch it.  A surviving mutant means the checks are blind to
that property, not that the mutant is harmless.

Mutants
-------
M1  drop `--check`            -> msgfmt stops validating catalogs
M2  compile into a wrong dir  -> .mo files never land next to their .po
M3  ignore the exit status    -> a broken catalog is reported as success
M4  remove the batching cap   -> JOBS is ignored (correctness unaffected)
M5  drop one locale           -> a catalog is silently skipped
M6  truncate the .mo          -> bytes differ from the sequential output
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "verify_patch"
GETTEXT = ROOT.parent / "tools" / "gettext" / "bin"
BASH = r"E:\Claw\WorkBuddy\resources\vendor\PortableGit\usr\bin\bash.exe"
SCRIPT_REL = "scripts/generate-translation-binaries.sh"

REFERENCE: dict[str, str] = {}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def mo_files(root: Path) -> list[Path]:
    return sorted(root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"))


def clean_mo(root: Path) -> None:
    for p in mo_files(root):
        p.unlink()


def run_script(root: Path) -> tuple[int, str, str]:
    env = {**os.environ, "PATH": str(GETTEXT) + os.pathsep + os.environ["PATH"]}
    proc = subprocess.run([BASH, SCRIPT_REL], cwd=root, env=env,
                          capture_output=True, text=True, errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def check_outputs(root: Path) -> list[str]:
    """The assertions a reviewer would make about a correct run."""
    problems = []
    files = mo_files(root)
    if len(files) != 36:
        problems.append(f"expected 36 .mo files, found {len(files)}")
    digests = {p.parent.parent.name: sha(p) for p in files}
    for locale, digest in REFERENCE.items():
        got = digests.get(locale)
        if got is None:
            problems.append(f"{locale}: missing")
        elif got != digest:
            problems.append(f"{locale}: bytes differ from sequential output")
    return problems


BROKEN_PO = b'msgid "x"\nmsgstr "y"\nBROKEN LINE HERE\n'


def check_rejects_broken_catalog(root: Path) -> list[str]:
    """A broken catalog must make the script exit non-zero.

    Without this case, mutants that stop validating (`--check` removed) or stop
    propagating the failure are invisible: on well-formed input they produce
    byte-identical output, so only bad input can tell them apart.
    """
    problems = []
    victim = root / "src/humanize/locale/de_DE/LC_MESSAGES/humanize.po"
    original = victim.read_bytes()
    try:
        victim.write_bytes(original + BROKEN_PO)
        clean_mo(root)
        rc, out, err = run_script(root)
        if rc == 0:
            problems.append("broken catalog was accepted (exit 0)")
        if "translation compilation failed" not in err:
            problems.append("no failure message on stderr")
    finally:
        victim.write_bytes(original)
    return problems


MUTANTS = {
    "M1_drop_check_flag": lambda s: s.replace("msgfmt --check -o", "msgfmt -o"),
    "M2_wrong_output_dir": lambda s: s.replace(
        '"src/humanize/locale/$locale/LC_MESSAGES/humanize.mo"',
        '"/tmp/mut_$locale.mo"'),
    "M3_ignore_exit_status": lambda s: s.replace(
        'wait "$pid" || failed=1', 'wait "$pid" || true'),
    "M4_ignore_jobs_cap": lambda s: s.replace(
        'if [ "$running" -ge "$JOBS" ]; then', 'if [ "$running" -ge 100000 ]; then'),
    "M5_skip_one_locale": lambda s: s.replace(
        '    locale="$(basename $d)"\n    echo "$locale"',
        '    locale="$(basename $d)"\n    [ "$locale" = "de_DE" ] && continue\n    echo "$locale"'),
}

# M6 corrupts the artifact after a successful compile, so it cannot be expressed
# as a text substitution.  It is the mutant that proves the byte comparison is
# actually comparing bytes and not just counting files.
POST_HOOKS = {
    "M6_truncate_output": lambda root: [
        p.write_bytes(p.read_bytes()[:64]) for p in mo_files(root)
    ],
}
MUTANTS["M6_truncate_output"] = lambda s: s  # no-op text change, applied via POST_HOOKS


def main() -> None:
    # Reference digests from the unmutated patched tree.
    clean_mo(BASE)
    rc, _, err = run_script(BASE)
    if rc != 0:
        raise SystemExit(f"baseline run failed: {err}")
    for p in mo_files(BASE):
        REFERENCE[p.parent.parent.name] = sha(p)
    assert len(REFERENCE) == 36, f"reference has {len(REFERENCE)} locales"

    baseline_problems = check_outputs(BASE)
    results = {
        "_baseline": {
            "problems": baseline_problems,
            "verdict": "clean" if not baseline_problems else "BROKEN HARNESS",
        },
        "mutants": {},
    }

    work = ROOT / "_mut"
    for name, mutate in MUTANTS.items():
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(BASE, work, ignore=shutil.ignore_patterns(
            ".git", "dist", "htmlcov", "__pycache__", "*.mo", "*.egg-info"))

        target = work / SCRIPT_REL
        original = target.read_text(encoding="utf-8")
        mutated = mutate(original)
        if mutated == original and name not in POST_HOOKS:
            results["mutants"][name] = {"status": "NOT APPLIED",
                                        "note": "mutation did not change the file"}
            continue
        if mutated != original:
            target.write_text(mutated, encoding="utf-8", newline="\n")

        rc, out, err = run_script(work)
        if name in POST_HOOKS:
            POST_HOOKS[name](work)
        problems = check_outputs(work)
        # The broken-catalog case only makes sense when the script still writes
        # to the real locale directories.
        if name != "M2_wrong_output_dir":
            problems += check_rejects_broken_catalog(work)

        killed = bool(problems) or rc != 0
        results["mutants"][name] = {
            "status": "KILLED" if killed else "SURVIVED",
            "exit_code": rc,
            "problems": problems[:4],
            "problem_count": len(problems),
        }

    if work.exists():
        shutil.rmtree(work)
    clean_mo(BASE)

    survived = [k for k, v in results["mutants"].items() if v["status"] == "SURVIVED"]
    results["_summary"] = {
        "total": len(results["mutants"]),
        "killed": sum(1 for v in results["mutants"].values() if v["status"] == "KILLED"),
        "survived": survived,
        "not_applied": [k for k, v in results["mutants"].items()
                        if v["status"] == "NOT APPLIED"],
    }
    text = json.dumps(results, indent=2)
    print(text)
    (ROOT / "evidence_mutation.json").write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
