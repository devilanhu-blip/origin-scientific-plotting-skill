"""Make the documented first preview using only the bundled SIMULATED example."""

import argparse
import subprocess
import sys
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "origin-alpha"
EXAMPLE_SHA256 = "c51448b1c1546a66db958e0404e42d17e6e2000b60a605583aac65c001cd1ad2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    command = [sys.executable, "-I", "-B", "-X", "utf8", str(SKILL / "scripts" / "origin_trial.py")]
    if args.config:
        command.extend(["--config", str(args.config)])
    if args.state_dir:
        command.extend(["--state-dir", str(args.state_dir)])
    command.extend([
        "draft", str(SKILL / "examples" / "SIMULATED_voltage.csv"),
        "--data-kind", "SIMULATED", "--group-by", "样品", "--sample", "薄膜 A",
        "--branch-by", "阶段", "--x", "温度 [K]", "--y", "电压 [mV]",
        "--y-error", "电压 [mV]", "电压绝对误差 [mV]", "模拟仪器给出的同单位对称绝对半宽",
        "--error-format", "absolute-half-width", "--visibility", "managed",
        "--kind", "linesymbol", "--preset", "清晰", "--title", "薄膜 A 升温与降温",
        "--expected-sha256", EXAMPLE_SHA256,
    ])
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
