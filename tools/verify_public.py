"""Check the proposed release paths, source identities, local links and image metadata."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import struct
from urllib.parse import unquote, urlsplit
import zlib


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "proposed-public-files.json"
HASHES = "sha256-inventory.json"
TEXT = {".py", ".md", ".txt", ".json", ".yml", ".csv"}


def fail(message):
    raise ValueError(message)


def release_path(name):
    path = PurePosixPath(name)
    if (not name or path.as_posix() != name or path.is_absolute() or "\\" in name
            or PureWindowsPath(name).drive or ".." in path.parts or ".git" in path.parts):
        fail(f"Invalid public path: {name}")
    local = ROOT / path
    if any(part.is_symlink() or part.is_junction() for part in (local, *local.parents) if part != ROOT.parent):
        fail(f"Linked path in release: {name}")
    if not local.is_file():
        fail(f"Missing public file: {name}")
    return local


def audit_png(data, name):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"Invalid PNG signature: {name}")
    chunks = []
    offset = 8
    while offset + 12 <= len(data):
        size, kind = struct.unpack_from(">I4s", data, offset)
        end = offset + size + 12
        if end > len(data) or kind not in {b"IHDR", b"IDAT", b"IEND"}:
            fail(f"Unexpected image metadata or invalid chunk length: {name}")
        if zlib.crc32(data[offset + 4:end - 4]) != struct.unpack_from(">I", data, end - 4)[0]:
            fail(f"PNG CRC mismatch: {name}")
        chunks.append(kind)
        offset = end
    if offset != len(data) or chunks[:1] != [b"IHDR"] or chunks[-1:] != [b"IEND"] or b"IDAT" not in chunks:
        fail(f"Incomplete PNG: {name}")


def check_links(source, contents, names):
    prose = re.sub(r"(?ms)^\s*[\x60]{3}.*?^\s*[\x60]{3}[^\n]*", "", contents)
    for raw in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", prose):
        target = urlsplit(raw)
        if target.scheme in {"http", "https"} and target.netloc:
            continue
        if target.scheme or target.netloc:
            fail(f"Unsupported link in {source.name}: {raw}")
        if target.path:
            dest = (source.parent / unquote(target.path)).resolve()
            if not dest.is_relative_to(ROOT) or dest.relative_to(ROOT).as_posix() not in names:
                fail(f"Link outside the release or missing in {source.name}: {raw}")


def check(strict, write):
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    names = [name for group in manifest["groups"] for name in group["files"]]
    if len(set(name.casefold() for name in names)) != len(names) or not {MANIFEST, HASHES}.issubset(names):
        fail("The public path list contains a collision or lacks its own release metadata.")
    if strict:
        actual = set()
        for base, directories, files in ROOT.walk():
            if base == ROOT and ".git" in directories:
                directories.remove(".git")
            for directory in directories:
                path = base / directory
                if path.is_symlink() or path.is_junction():
                    fail(f"Unexpected linked directory: {path.relative_to(ROOT)}")
            actual.update((base / f).relative_to(ROOT).as_posix() for f in files)
        if actual != set(names):
            fail(f"Unexpected files: {sorted(actual - set(names))}; missing: {sorted(set(names) - actual)}")
    digests = {}
    for name in sorted(set(names) - {HASHES}):
        path = release_path(name)
        data = path.read_bytes()
        if path.suffix == ".png":
            audit_png(data, name)
        elif path.suffix in TEXT or path.name in {".gitignore", ".gitattributes", "LICENSE"}:
            source = data.decode("utf-8-sig")
            if "\0" in source:
                fail(f"Unexpected binary content: {name}")
            if path.suffix == ".md":
                check_links(path, source, set(names))
        else:
            fail(f"Unexpected public file type: {name}")
        digests[name] = hashlib.sha256(data).hexdigest()
    if write:
        (ROOT / HASHES).write_text(json.dumps(digests, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8", newline="\n")
    else:
        actual = json.loads(release_path(HASHES).read_text(encoding="utf-8"))
        if digests != actual:
            changed = sorted(k for k in digests.keys() | actual.keys() if digests.get(k) != actual.get(k))
            fail(f"Unexpected SHA-256 or path: {changed}")
    print(f"Verified {len(names)} public paths, document links, PNG chunks and the checksum inventory.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Also reject unlisted files in a clean checkout.")
    parser.add_argument("--write-hashes", action="store_true", help="Refresh the hashes after reviewing changes.")
    args = parser.parse_args()
    try:
        check(args.strict, args.write_hashes)
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
