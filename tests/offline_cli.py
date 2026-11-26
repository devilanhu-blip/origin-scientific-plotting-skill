"""Shared command-line example for the offline regression tests and gallery."""

import json
import os
from pathlib import Path
import subprocess
import sys


SKILL = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "origin-alpha"
CLI = SKILL / "scripts" / "origin_trial.py"
CSV = SKILL / "examples" / "SIMULATED_voltage.csv"
PROFILES = ("clean", "mono", "汇报")
X = "温度 [K]"
Y = "电压 [mV]"
ERROR = "电压绝对误差 [mV]"
DEFINITION = "模拟仪器给出的同单位对称绝对半宽"


def run_cli(cwd, state, *args):
    config = os.environ.get("ORIGIN_ALPHA_TEST_CONFIG")
    config_args = ["--config", str(Path(config).absolute())] if config else []
    return subprocess.run(
        [sys.executable, "-I", "-B", "-X", "utf8", str(CLI), *config_args,
         "--state-dir", str(state), *map(str, args)],
        cwd=cwd, capture_output=True, encoding="utf-8", timeout=30, check=False,
    )


def example_options(*, y=Y, error=ERROR, definition=DEFINITION):
    return [
        "--data-kind", "SIMULATED", "--group-by", "样品", "--sample", "薄膜 A", "--branch-by", "阶段",
        "--x", X, "--y", y, "--y-error", y, error, definition,
        "--error-format", "absolute-half-width", "--visibility", "managed", "--kind", "linesymbol",
    ]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))
