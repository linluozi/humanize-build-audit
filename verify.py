#!/usr/bin/env python3
"""Acceptance check for the humanize build-flow optimisation.

Run from anywhere:

    python verify.py            # full check (needs a compiler for .po files)
    python verify.py --quick    # skip the wheel build

The script does not assume this tree's layout: it finds the project root by
looking for a marker file, creates its own virtualenv, and builds everything it
needs from scratch.  It never reads anything outside the extracted archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKERS = ("pyproject.toml", "tox.ini", "src/humanize/__init__.py")

N_LOCALES = 36
EXPECTED_COUNTS = (854, 2)  # passed, skipped, on the untouched upstream

ANSI = re.compile(r"\x1b\[[0-9;]*m")
COUNTS = re.compile(r"(\d+) passed(?:, (\d+) skipped)?")

results: list[tuple[bool, str, str]] = []


def record(ok: bool, name: str, detail: str = "") -> None:
    results.append((ok, name, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""))


def find_root() -> Path:
    """Locate the project root.

    Supports the archive layout (`verify.py` next to `project/`) as well as a
    copy of `verify.py` dropped straight into the project, so the check keeps
    working however the archive is unpacked.
    """
    for candidate in (HERE / "project", HERE, *HERE.parents):
        if all((candidate / m).exists() for m in MARKERS):
            return candidate
    raise SystemExit(
        "cannot find the project root; expected " + ", ".join(MARKERS)
    )


def find_bash() -> str:
    """Resolve a POSIX shell that is not the WSL launcher in System32.

    `bash` on PATH can be C:\\Windows\\System32\\bash.exe, which is the WSL stub
    and prints UTF-16 errors when no distribution is installed.
    """
    if os.name != "nt":
        return shutil.which("bash") or "/bin/bash"
    for cand in (
        r"E:\Claw\WorkBuddy\resources\vendor\PortableGit\usr\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
    ):
        if Path(cand).exists():
            return cand
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    raise SystemExit("no usable bash found (Git Bash is required)")


def find_msgfmt(root: Path) -> tuple[str | None, Path | None]:
    """Return (msgfmt command, directory to prepend to PATH).

    Search order: PATH, then an explicit GETTEXT_BIN/GETTEXT_HOME, then a
    gettext tree bundled next to the project (either at the archive root or
    inside the project).
    """
    for name in ("msgfmt", "msgfmt.exe"):
        p = shutil.which(name)
        if p:
            return p, Path(p).parent

    candidates: list[Path] = []
    for env in ("GETTEXT_BIN", "GETTEXT_HOME"):
        val = os.environ.get(env)
        if val:
            base = Path(val)
            candidates += [base / "bin" / "msgfmt.exe", base / "bin" / "msgfmt",
                           base / "msgfmt.exe", base / "msgfmt"]
    for base in (root, root.parent, HERE, HERE.parent):
        for sub in ("tools/gettext", "gettext", "vendor/gettext"):
            candidates += [base / sub / "bin" / "msgfmt.exe",
                           base / sub / "bin" / "msgfmt"]

    for cand in candidates:
        if cand.exists():
            return str(cand), cand.parent
    return None, None


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                          text=True, errors="replace")
    if check and proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
        )
    return proc


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ensure_version_source(root: Path) -> str:
    """Make the version resolvable for a tree that has no git history.

    The project derives its version from git tags via hatch-vcs, so an
    unpacked archive cannot be built until there is a tag to read.  CI always
    has a real checkout; a fresh extraction does not.  Initialise a throwaway
    repository with a tag, which is what a maintainer would get from
    `git clone`, and leave an existing history alone.
    """
    git = shutil.which("git")
    if git is None:
        os.environ.setdefault("SETUPTOOLS_SCM_PRETEND_VERSION", "4.0.0")
        return "SETUPTOOLS_SCM_PRETEND_VERSION=4.0.0 (git not available)"

    inside = run([git, "rev-parse", "--is-inside-work-tree"], root, check=False)
    if inside.returncode == 0 and inside.stdout.strip() == "true":
        tag = run([git, "describe", "--tags"], root, check=False)
        if tag.returncode == 0:
            return f"existing git history, {tag.stdout.strip()}"
        run([git, "tag", "v4.0.0"], root, check=False)
        return "existing git history, added tag v4.0.0"

    run([git, "init", "--quiet", "--initial-branch", "main"], root)
    run([git, "-c", "user.email=verify@local", "-c", "user.name=verify",
         "add", "--all"], root)
    run([git, "-c", "user.email=verify@local", "-c", "user.name=verify",
         "commit", "--quiet", "--message", "archive snapshot"], root)
    run([git, "tag", "v4.0.0"], root)
    return "initialised a local repository with tag v4.0.0"


def force_rmtree(path: Path) -> None:
    """Remove a tree, clearing read-only bits first.

    git marks pack files read-only, and on Windows `shutil.rmtree` then fails
    silently through its error handler, leaving a half-deleted `.git` behind.
    """
    def onerror(func, target, exc_info):  # noqa: ANN001
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=onerror)
    if path.exists():
        for p in path.rglob("*"):
            try:
                os.chmod(p, 0o700)
            except OSError:
                pass
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the wheel build")
    ap.add_argument("--keep", action="store_true", help="keep the temporary venv")
    args = ap.parse_args()

    root = find_root()
    print(f"project root: {root}")

    bash = find_bash()
    msgfmt, gettext_dir = find_msgfmt(root)
    print(f"bash:    {bash}")
    print(f"msgfmt:  {msgfmt or 'NOT FOUND'}")

    # ---------------------------------------------------------------- layout
    record((root / "scripts/generate-translation-binaries.sh").exists(),
           "patched compile script is present")
    patch_file = HERE / "patch" / "build-redundancy.patch"
    record(patch_file.exists() or (root / "patch" / "build-redundancy.patch").exists(),
           "patch file is present")

    # The bundled pristine tree must really be pristine: an archive that ships
    # an already-patched "upstream" makes the patch look broken when it is not.
    upstream = HERE / "patch" / "upstream"
    if upstream.is_dir():
        touched = ["scripts/generate-translation-binaries.sh", "tox.ini",
                   ".gitignore", ".github/workflows/test.yml"]
        same = [f for f in touched
                if (upstream / f).exists() and (root / f).exists()
                and (upstream / f).read_bytes() == (root / f).read_bytes()]
        record(not same, "bundled upstream tree is unpatched",
               f"identical to project: {same}" if same else "4 files differ as expected")
        record((upstream / "scripts/generate-translation-binaries.sh")
               .read_bytes().count(b"JOBS") == 0,
               "bundled upstream compile script has no patch markers")

        # Prove the patch reproduces the shipped tree, which is the whole
        # promise of shipping a patch rather than only a diff of a working copy.
        work = Path(tempfile.mkdtemp(prefix="humanize-patch-"))
        try:
            copy = work / "upstream"
            shutil.copytree(upstream, copy)
            proc = run(["patch", "--binary", "-p1", "-i", str(patch_file)],
                       copy, check=False)
            record(proc.returncode == 0, "patch applies to the pristine tree",
                   f"exit {proc.returncode}")
            identical = [f for f in touched
                         if (copy / f).read_bytes() == (root / f).read_bytes()]
            record(len(identical) == len(touched),
                   "patch reproduces the shipped tree byte for byte",
                   f"{len(identical)}/{len(touched)} files")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    if msgfmt is None:
        print("\nmsgfmt is required: install gettext (Linux/macOS) or "
              "`choco install gettext` (Windows), or set GETTEXT_BIN.")
        return 2

    env = dict(os.environ)
    env["PATH"] = str(gettext_dir) + os.pathsep + env.get("PATH", "")
    env.pop("COVERAGE_FILE", None)

    # ------------------------------------------------- compile translations
    for p in root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"):
        p.unlink()

    proc = run([bash, "scripts/generate-translation-binaries.sh"], root, env)
    mo = sorted(root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"))
    record(len(mo) == N_LOCALES, "compiles every catalog",
           f"{len(mo)}/{N_LOCALES} .mo files")

    echoed = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    record(echoed == sorted(p.parent.parent.name for p in mo),
           "echoes locale names in sorted order",
           f"{len(echoed)} lines")

    # ----------------------------------------------------- determinism check
    digests = {p.parent.parent.name: sha(p) for p in mo}
    for p in mo:
        p.unlink()
    run([bash, "scripts/generate-translation-binaries.sh"], root, env)
    again = {p.parent.parent.name: sha(p) for p in
             root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo")}
    record(digests == again, "output is reproducible byte for byte",
           f"{len(again)} locales compared")

    # -------------------------------------------- rejects a broken catalog
    victim = root / "src/humanize/locale/de_DE/LC_MESSAGES/humanize.po"
    original = victim.read_bytes()
    try:
        victim.write_bytes(original + b'msgid "x"\nmsgstr "y"\nBROKEN LINE\n')
        for p in root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"):
            p.unlink()
        proc = run([bash, "scripts/generate-translation-binaries.sh"], root, env,
                   check=False)
        record(proc.returncode != 0, "rejects a malformed catalog",
               f"exit {proc.returncode}")
        record("translation compilation failed" in proc.stderr,
               "reports the failure on stderr")
    finally:
        victim.write_bytes(original)
        for p in root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"):
            p.unlink()
        run([bash, "scripts/generate-translation-binaries.sh"], root, env)

    # ------------------------------------------------------------- test run
    venv = Path(tempfile.mkdtemp(prefix="humanize-verify-"))
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    created_git = False
    try:
        version_source = ensure_version_source(root)
        created_git = version_source.startswith("initialised")
        record(True, "version source prepared", version_source)
        run([sys.executable, "-m", "venv", str(venv)], root)
        pip = [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
        index = os.environ.get("PIP_INDEX_URL", "")
        extra = ["-i", index] if index else []
        run([*pip, *extra, "-e", ".", "pytest>=9", "pytest-cov",
             "freezegun", "pytest-benchmark"], root)

        patched = run([str(py), "-m", "pytest", "-q", "--benchmark-disable",
                       "--cov", "humanize", "--cov", "tests",
                       "--cov-report", "term", "--cov-report", "xml",
                       "-p", "no:cacheprovider"], root)
        counts = COUNTS.search(ANSI.sub("", patched.stdout))
        got = (int(counts.group(1)), int(counts.group(2) or 0)) if counts else None
        record(got == EXPECTED_COUNTS, "full test suite matches upstream counts",
               f"{got} vs expected {EXPECTED_COUNTS}")

        record(not (root / "htmlcov").exists(),
               "no htmlcov written by the test command")

        # A missing catalog must not look green.
        for p in root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"):
            p.unlink()
        degraded = run([str(py), "-m", "pytest", "-q", "--benchmark-disable",
                        "-p", "no:cacheprovider"], root, check=False)
        dcounts = COUNTS.search(ANSI.sub("", degraded.stdout))
        dgot = (int(dcounts.group(1)), int(dcounts.group(2) or 0)) if dcounts else None
        record(dgot is not None and dgot[1] > 10,
               "missing catalogs show up as skips, not silence",
               f"{dgot} without .mo")
        run([bash, "scripts/generate-translation-binaries.sh"], root, env)

        # -------------------------------------------------------- wheel build
        if not args.quick:
            dist = root / "dist"
            force_rmtree(dist) if dist.exists() else None
            run([str(py), "-m", "pip", "install", "--quiet", "build"], root)
            run([str(py), "-m", "build", "--wheel"], root)
            wheels = sorted(dist.glob("*.whl"))
            record(len(wheels) == 1, "wheel builds", wheels[0].name if wheels else "")

            if wheels:
                import zipfile
                with zipfile.ZipFile(wheels[0]) as z:
                    names = z.namelist()
                    mo_in_wheel = [n for n in names if n.endswith(".mo")]
                    record(len(mo_in_wheel) == N_LOCALES,
                           "wheel ships every compiled catalog",
                           f"{len(mo_in_wheel)}/{N_LOCALES}")
                    pyz = [n for n in names if n.endswith(".py")]
                    record(len(pyz) > 0, "wheel ships the package",
                           f"{len(pyz)} .py files")

                site = venv / ("Lib/site-packages" if os.name == "nt"
                               else f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
                with zipfile.ZipFile(wheels[0]) as z:
                    z.extractall(site)
                smoke = run([str(py), "-c",
                             "import humanize, datetime as dt;"
                             "humanize.i18n.activate('de_DE');"
                             "a = humanize.intcomma(10000000);"
                             "humanize.i18n.activate('zh_CN');"
                             "b = humanize.naturaltime(dt.datetime.now()-dt.timedelta(seconds=3));"
                             "humanize.i18n.deactivate();"
                             "c = humanize.intcomma(10000000);"
                             "print(a); print(b); print(c)"], root)
                lines = [ln.strip() for ln in smoke.stdout.splitlines() if ln.strip()]
                record(lines[-3:] == ["10.000.000", "3秒之前", "10,000,000"],
                       "installed wheel translates correctly", " / ".join(lines[-3:]))
    finally:
        if not args.keep:
            shutil.rmtree(venv, ignore_errors=True)
        # Leave the tree as it was found: the checks create a venv, a wheel and
        # (for an archive without history) a throwaway git repo.
        for name in ("dist", "htmlcov", ".coverage", "coverage.xml",
                     ".pytest_cache", ".benchmarks"):
            p = root / name
            if p.is_dir():
                force_rmtree(p)
            elif p.exists():
                p.unlink()
        if created_git:
            force_rmtree(root / ".git")
        for p in root.glob("src/humanize/locale/*/LC_MESSAGES/*.mo"):
            p.unlink()
        (root / "src/humanize/_version.py").unlink(missing_ok=True)
        for cache in root.rglob("__pycache__"):
            force_rmtree(cache)

    # ------------------------------------------------------------- summary
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    if passed != total:
        print("\nfailed checks:")
        for ok, name, detail in results:
            if not ok:
                print(f"  - {name} ({detail})")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
