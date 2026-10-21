# NOTICE

This repository contains a modified copy of
[`python-humanize/humanize`](https://github.com/python-humanize/humanize),
taken at commit `785e5dcc0d0308ad0dff3f6cc0faa7085ad0375b` (2026-10-06).

- Upstream licence: MIT. The original `LICENCE` file is reproduced unchanged as
  `LICENSE` at the repository root, and byte-for-byte identical copies are kept
  inside `project/` and `patch/upstream/`.
- The modifications are limited to the build and test flow: `tox.ini`,
  `scripts/generate-translation-binaries.sh`, `.gitignore` and
  `.github/workflows/test.yml`. No library code under `src/humanize/` was
  changed. The exact change is in `patch/build-redundancy.patch`.
- `patch/upstream/` is the unmodified upstream tree, included so the patch can
  be replayed and verified. `project/` is the patched tree.

Nothing here is an official release of humanize, and the upstream maintainers
have not reviewed it.
