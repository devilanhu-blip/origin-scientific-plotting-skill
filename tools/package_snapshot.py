"""Assemble a deterministic release ZIP from the checked, explicit public inventory."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def build_in(staging):
    subprocess.run([sys.executable, "-I", "-B", "-X", "utf8",
                    str(ROOT / "tools" / "verify_public.py")], check=True)
    inventory = json.loads((ROOT / "proposed-public-files.json").read_text(encoding="utf-8"))
    hashes = json.loads((ROOT / "sha256-inventory.json").read_text(encoding="utf-8"))
    names = sorted(name for group in inventory["groups"] for name in group["files"])
    version = inventory["candidate"]
    folder = "origin-scientific-plotting-skill-" + version
    staging.mkdir()
    asset = staging / (folder + ".zip")
    with zipfile.ZipFile(asset, "x") as archive:
        for name in names:
            data = (ROOT / name).read_bytes()
            if name in hashes and hashlib.sha256(data).hexdigest() != hashes[name]:
                raise ValueError(f"File changed during packaging: {name}")
            member = zipfile.ZipInfo(folder + "/" + name, date_time=(2026, 11, 26, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            archive.writestr(member, data)
    with zipfile.ZipFile(asset) as archive:
        if archive.testzip() or archive.namelist() != [folder + "/" + name for name in names]:
            raise ValueError("ZIP member list or CRC differs from the public snapshot.")
        for name in names:
            member = archive.getinfo(folder + "/" + name)
            if member.comment or member.extra or archive.read(member) != (ROOT / name).read_bytes():
                raise ValueError(f"The archived member differs from the reviewed source: {name}")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    (staging / (asset.name + ".sha256")).write_text(digest + "  " + asset.name + "\n",
                                                   encoding="ascii", newline="\n")
    return asset.name, digest, len(names)


def package(output):
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Choose a new destination for this release rehearsal.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".packing-", dir=output.parent) as scratch:
        staged = Path(scratch) / "release"
        name, digest, count = build_in(staged)
        staged.rename(output)
    return {"asset": str(output / name), "sha256": digest, "members": count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory outside the checkout.")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        parser.error("Choose a new output directory outside the checkout.")
    try:
        print(json.dumps(package(args.output), ensure_ascii=False))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + "\n")
