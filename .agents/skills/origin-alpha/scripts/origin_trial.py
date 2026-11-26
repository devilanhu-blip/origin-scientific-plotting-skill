"""Command-line entry point for the portable offline Alpha."""

import argparse
import json
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True


def load_runtime():
    # Import only the adjacent source package. Never search a historical installation.
    base = Path(__file__).absolute().parents[1] / "runtime"
    pkg = base / "m4plot"
    cache = base / ".offline-empty-cache"
    for path in (*reversed(pkg.parents), pkg, Path(__file__).absolute(), *pkg.glob("*.py"), cache):
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0)
                                & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError(f"Choose a local checkout without redirected files or folders: {path}")
    if cache.exists():
        raise ValueError("The offline source-cache isolation directory must be absent.")
    sys.pycache_prefix = str(cache)
    sys.path.insert(0, str(base))
    try:
        import m4plot
    finally:
        sys.path.pop(0)
    if Path(m4plot.__file__) != pkg / "__init__.py" or m4plot.__version__ != "0.1.0-alpha.1":
        raise ValueError("The adjacent offline package version does not match this CLI.")


def parser():
    from m4plot.legend_layout import POSITIONS

    p = argparse.ArgumentParser(description="Offline CSV inspection, plotting plans and PNG previews.")
    p.add_argument("--config", type=Path, help="Optional JSON config; its relative paths use its own folder.")
    p.add_argument("--state-dir", type=Path, help="Local output and style library (default .origin-alpha).")
    actions = p.add_subparsers(dest="action", required=True)
    actions.add_parser("doctor", help="Check interpreter, Pillow, bundled presets and preview fonts, read-only.")
    actions.add_parser("presets", help="List clean, mono, 汇报 and saved personal/lab styles.")
    inspect = actions.add_parser("inspect", help="Show exact CSV headers, row count and source SHA-256.")
    inspect.add_argument("source", type=Path)
    draft = actions.add_parser("draft", help="Create a fresh preview from a CSV or restyle a checked draft.")
    draft.add_argument("source", type=Path)
    draft.add_argument("--data-kind", choices=("MEASURED", "SIMULATED"))
    draft.add_argument("--expected-sha256", help="Bind to the exact source bytes previously inspected.")
    draft.add_argument("--x", metavar="HEADER")
    draft.add_argument("--y", action="append", metavar="HEADER")
    draft.add_argument("--y-error", action="append", nargs=3, metavar=("Y", "ERROR", "DEFINITION"))
    draft.add_argument("--error-format", choices=("absolute-half-width",))
    draft.add_argument("--column", action="append", nargs=3, metavar=("HEADER", "QUANTITY", "UNIT"))
    draft.add_argument("--group-by", metavar="HEADER")
    draft.add_argument("--branch-by", metavar="HEADER")
    draft.add_argument("--sample", action="append")
    draft.add_argument("--preset", help="Builtin name or a saved selector such as 实验室#1/名称.")
    draft.add_argument("--kind", choices=("scatter", "line", "linesymbol"))
    draft.add_argument("--title")
    draft.add_argument("--legend", choices=sorted(POSITIONS))
    draft.add_argument("--set", dest="adjust", action="append", nargs=2, metavar=("PROPERTY", "VALUE"))
    draft.add_argument("--series", action="append", nargs=3, metavar=("SERIES", "PROPERTY", "VALUE"))
    draft.add_argument("--segment", action="append", nargs=3, metavar=("STAGE", "PROPERTY", "VALUE"))
    draft.add_argument("--label", action="append", nargs=2, metavar=("SERIES", "LABEL"))
    preview = actions.add_parser("preview", help="Verify the original source, plan, style and saved preview.")
    preview.add_argument("source", type=Path)
    for command in (draft, preview):
        command.add_argument("--visibility", required=True, choices=("managed",),
                             help="Record the chosen two-series policy in this offline preview.")
    save = actions.add_parser("save-style", help="Create a named style or append a version.")
    save.add_argument("source", type=Path, help="Verified draft folder in the current state directory.")
    save.add_argument("name", help="个人/名称 or 实验室/名称")
    save.add_argument("--update-from", type=int, help="Append only if this is still the current version.")
    history = actions.add_parser("history", help="List pinned versions of a saved style, newest first.")
    history.add_argument("name")
    return p


def main():
    try:
        load_runtime()
        from m4plot.offline import run

        result = run(parser().parse_args())
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 2 if result.get("status") == "OFFLINE_DEPENDENCY_MISSING" else 0
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

