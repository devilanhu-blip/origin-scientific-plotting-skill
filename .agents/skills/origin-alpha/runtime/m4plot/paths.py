"""Check local file paths and their ancestors before opening or publishing."""

from pathlib import Path
import os
import re
import stat
import unicodedata


def require(value, message):
    if not value:
        raise ValueError(message)


def plain_path(path):
    """Reject redirects even on intermediate Windows path components."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "Expected an absolute literal path")
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        require(not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                and not stat.S_ISLNK(info.st_mode), f"Reparse point is not allowed: {component}")
    return path


def local_path(path):
    """Reject device, redirected, network and ambiguous paths before opening a selection."""
    require(isinstance(path, (str, os.PathLike)) and bool(str(path).strip()), "请选择有效的本地路径。")
    path = Path(path)
    require(not path.drive or path.is_absolute(), "请使用完整的盘符路径。")
    require(not path.root or path.is_absolute(), "路径缺少盘符。")
    require(".." not in path.parts, "路径不可包含上级目录跳转。")
    path = path.absolute()
    require(re.fullmatch(r"[a-zA-Z]:", path.drive), "须使用本机普通磁盘路径。")
    for part in path.parts[1:]:
        require(not any(char in '<>:"/\\|?*' or unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
                        for char in part)
                and not part.endswith((" ", ".")) and not Path(part).is_reserved(),
                "路径包含设备名、数据流或其他非普通文件名。")
    return plain_path(path)
