# Contributing to the offline Alpha

Report ordinary bugs or propose changes through GitHub Issues. Use the bundled simulated CSV to reproduce changes. Describe the input columns, units, row order, error definition, selected style and actual output. Share a minimal synthetic fixture when a new regression requires different data. [GitHub Issues](https://github.com/devilanhu-blip/origin-scientific-plotting-skill/issues)

Use UTF-8 and a separate virtual environment. Run the tests and verify the snapshot from the repository root.

```powershell
.\.venv\Scripts\python.exe -I -B -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -I -B -X utf8 tools/verify_public.py
```

By submitting original material for inclusion, you agree to license that contribution under the project's MIT License. Identify any third-party material and its terms for maintainer review. [Project license](LICENSE) · [Licensing scope](docs/licensing.md)

A maintainer reviews each new public file for provenance and rights before adding its exact path to the allowlist. After an intentional release change, regenerate the inventory checksums with `tools/verify_public.py --write-hashes`, review the differences, and run `tools/verify_public.py --strict` in the clean release working copy. [Public file list](proposed-public-files.json)

To rehearse release packaging, run `.\.venv\Scripts\python.exe -I -B -X utf8 tools/package_snapshot.py ../alpha-release-review` with a fresh destination. It creates a ZIP only from the reviewed paths, checks its contents and CRC, and writes a separate SHA-256 file. Compare the asset hash with the publisher's recorded release hash before use.

The CI workflow targets disposable GitHub-hosted Windows runners using read-only repository permissions. Keep submissions away from private research directories and licensed native workstations. Report sensitive issues using the [security procedure](SECURITY.md).
