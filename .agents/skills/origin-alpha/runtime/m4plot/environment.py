"""Configuration and read-only diagnostics for the public Windows offline candidate."""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import struct
import sys

from .common import fields, read_json
from .paths import local_path, require

PILLOW_VERSION = "12.3.0"


@dataclass(frozen=True)
class Environment:
    state: Path
    regular: Path | None
    bold: Path | None

    @property
    def library(self):
        return local_path(self.state / "styles" / "personal")


def resolve_environment(config, state_dir):
    values = {}
    base = Path.cwd()
    if config is not None:
        path = local_path(config)
        base, values = path.parent, read_json(path)
        fields(values, "config", (), ("state_dir", "font_regular", "font_bold"))
        for key, value in values.items():
            require(isinstance(value, str) and value.strip(), f"配置项 {key} 需要有效的本地路径。")
    def configured_path(value):
        path = Path(value)
        return local_path(path if path.anchor else base / path)

    state = local_path(state_dir) if state_dir is not None else configured_path(values.get("state_dir", ".origin-alpha"))
    skill = Path(__file__).absolute().parents[2]
    require(state != Path(state.anchor) and not state.is_relative_to(skill) and not skill.is_relative_to(state),
            "请从仓库根目录运行，或用 --state-dir 指定 Skill 目录外的独立状态目录。")
    require(not state.exists() or state.is_dir(), "请将 state_dir 指向独立的目录。")
    system = os.environ.get("SystemRoot")
    def font(key, default):
        if key in values:
            return configured_path(values[key])
        return local_path(Path(system) / "Fonts" / default) if system else None
    return Environment(state, font("font_regular", "msyh.ttc"), font("font_bold", "msyhbd.ttc"))


def supported_interpreter():
    return (sys.platform == "win32" and sys.implementation.name == "cpython"
            and sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8
            and platform.machine().upper() in {"AMD64", "X86_64"})


def doctor(env):
    """Load preview resources in memory. Do not create the state folder or open Origin."""
    from .styles import _load_preset

    issues = []
    if not supported_interpreter():
        issues.append("Select Windows x64 CPython 3.12 and run this CLI with that interpreter.")
    for preset in ("clean", "mono"):
        _load_preset(preset)
    pillow = pillow_path = None
    try:
        import PIL
        from PIL import Image, ImageDraw, ImageFont
        pillow = PIL.__version__
        pillow_path = str(Path(PIL.__file__).absolute())
        if pillow != PILLOW_VERSION:
            raise ImportError(f"expected {PILLOW_VERSION}, found {pillow}")
    except (OSError, ImportError) as exc:
        issues.append(f"Install the pinned wheel in the selected environment: "
                      f"python -m pip install --only-binary=:all: -r requirements.txt ({exc})")
    else:
        for key, face in (("font_regular", env.regular), ("font_bold", env.bold)):
            try:
                if face is None or not face.is_file():
                    raise OSError("file missing")
                ImageFont.truetype(str(face), 18)
            except (OSError, ValueError) as exc:
                issues.append(f"Set {key} in --config to a readable local CJK TrueType/OpenType font ({exc}).")
    return {
        "status": "OFFLINE_READY" if not issues else "OFFLINE_DEPENDENCY_MISSING",
        "python": platform.python_version(), "interpreter": sys.executable,
        "system": platform.system(), "machine": platform.machine(), "pillow": pillow, "pillow_path": pillow_path,
        "font_regular": str(env.regular) if env.regular else None,
        "font_bold": str(env.bold) if env.bold else None,
        "state_dir": str(env.state), "native_execution": "NOT_EXECUTED", "issues": issues,
    }

