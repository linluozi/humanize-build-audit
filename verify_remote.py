"""Verify the pushed repository byte for byte, without a git clone.

`git clone` is unreliable on this network, so instead: walk the remote tree via
the Git Data API, fetch every blob, and compare its SHA-256 with the local file.
A single mismatch fails the check.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = "linluozi/humanize-build-audit"
LOCAL = Path(__file__).resolve().parent
TOKEN = subprocess.run(["gh", "auth", "token", "--user", "linluozi"],
                       capture_output=True, text=True).stdout.strip()


def api(path: str) -> dict:
    r = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: Bearer {TOKEN}",
         "-H", "Accept: application/vnd.github+json",
         "--max-time", "90", f"https://api.github.com/repos/{REPO}/{path}"],
        capture_output=True,
    )
    return json.loads(r.stdout)


def main() -> int:
    ref = api("git/ref/heads/main")
    head = ref["object"]["sha"]
    commit = api(f"git/commits/{head}")
    tree_sha = commit["tree"]["sha"]
    tree = api(f"git/trees/{tree_sha}?recursive=1")

    blobs = [t for t in tree["tree"] if t["type"] == "blob"]
    print(f"remote commit {head[:10]}, {len(blobs)} files")

    local_files = {p.relative_to(LOCAL).as_posix(): p
                   for p in LOCAL.rglob("*") if p.is_file()}
    local_files.pop(".git", None)
    local_files = {k: v for k, v in local_files.items() if not k.startswith(".git/")}

    missing_local = sorted(set(t["path"] for t in blobs) - set(local_files))
    extra_local = sorted(set(local_files) - set(t["path"] for t in blobs))

    diffs = []
    checked = 0
    for t in blobs:
        path = t["path"]
        if path not in local_files:
            continue
        local = local_files[path].read_bytes()
        if hashlib.sha1(b"blob %d\0" % len(local) + local).hexdigest() == t["sha"]:
            checked += 1
            continue
        # Fall back to fetching the content, so a mismatch is confirmed rather
        # than assumed from the git object hash.
        blob = api(f"git/blobs/{t['sha']}")
        remote = base64.b64decode(blob["content"])
        if hashlib.sha256(remote).hexdigest() == hashlib.sha256(local).hexdigest():
            checked += 1
        else:
            diffs.append(path)

    print(f"verified {checked}/{len(blobs)} files byte-identical")
    if missing_local:
        print(f"only on remote: {missing_local}")
    if extra_local:
        print(f"only locally:  {extra_local}")
    if diffs:
        print(f"CONTENT DIFFERS: {diffs}")

    ok = not diffs and not missing_local and not extra_local
    print("\nREMOTE MATCHES LOCAL" if ok else "\nMISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
