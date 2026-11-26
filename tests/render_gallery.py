"""Reproduce the three official SIMULATED gallery previews using the public CLI."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from offline_cli import CSV, PROFILES, example_options, read_json, run_cli


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New destination directory")
    destination = parser.parse_args().output.absolute()
    if destination.exists():
        parser.error("Choose a new destination directory.")

    previews = {}
    with TemporaryDirectory(prefix="origin-alpha-gallery-") as scratch:
        cwd = Path(scratch)
        state = cwd / "offline-state"

        def invoke(*args):
            result = run_cli(cwd, state, *args)
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            return json.loads(result.stdout)

        info = invoke("inspect", CSV)
        snapshots = {"kind": "SIMULATED", "artifact_type": "OFFLINE_PREVIEW", "source_sha256": info["sha256"],
                     "common_segment_option": ["降温", "symbol", "square"], "profiles": {}}
        for profile, slug in zip(PROFILES, ("clean", "mono", "presentation"), strict=True):
            receipt = invoke("draft", CSV, *example_options(), "--expected-sha256", info["sha256"],
                             "--preset", profile, "--segment", "降温", "symbol", "square")
            if receipt["status"] != "OFFLINE_PREVIEW" or receipt["style_name"] != profile:
                raise RuntimeError(f"Unexpected preview receipt for {profile}.")
            draft = Path(receipt["draft"])
            preview, = receipt["previews"]
            filename = f"SIMULATED-{slug}-offline-preview.png"
            previews[filename] = Path(preview)
            snapshots["profiles"][profile] = {
                "image": filename, "image_sha256": sha256(Path(preview).read_bytes()).hexdigest(),
                "science_digest": receipt["science_digest"], "plan_digest": receipt["plan_digest"],
                "plan": read_json(draft / "plan.json"), "style_snapshot": read_json(draft / "style.json"),
            }
        records = snapshots["profiles"].values()
        if len({record["science_digest"] for record in records}) != 1:
            raise RuntimeError("The profiles changed the science digest.")
        destination.mkdir(parents=True)
        for filename, source in previews.items():
            shutil.copyfile(source, destination / filename)
        (destination / "snapshots.json").write_text(
            json.dumps(snapshots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )


if __name__ == "__main__":
    main()
