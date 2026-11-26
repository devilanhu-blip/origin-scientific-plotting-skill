"""Fetch the two pinned, openly licensed CJK fonts into a fresh CI-only directory."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


BASE = "https://raw.githubusercontent.com/notofonts/noto-cjk/523d033d6cb47f4a80c58a35753646f5c3608a78/Sans/OTF/SimplifiedChinese/"
WEIGHTS = {
    "Regular": "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b",
    "Bold": "b5f0d1a190a7f9b43c310a8850630af12553df32c4c050543f9059732d9b4c0a",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    directory.mkdir(parents=True, exist_ok=False)
    config = {}
    for weight, checksum in WEIGHTS.items():
        name = f"NotoSansCJKsc-{weight}.otf"
        with urlopen(BASE + name, timeout=45) as source:
            data = source.read(32 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError(f"Unexpected font bytes for {name}. Start again in a fresh directory.")
        (directory / name).write_bytes(data)
        config["font_" + weight.lower()] = name
    (directory / "fonts.json").write_text(json.dumps(config, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
