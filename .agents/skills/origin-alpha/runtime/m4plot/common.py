"""Byte identities, strict JSON and small contract helpers shared by the planner."""

import hashlib
import json
import os
import stat
from .paths import local_path, require
import re
import unicodedata


class InputError(ValueError):
    def __init__(self, code, field, message):
        self.code, self.field, self.message = code, field, message
        super().__init__(f"{code} [{field}] {message}")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def figure_title(data, figure):
    title = figure["title"]
    if data["kind"] == "SIMULATED" and not re.match(r"^SIMULATED(?:$|[^A-Za-z0-9])", title, re.I):
        return "SIMULATED | " + title
    return title


def digest(obj):
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode("utf-8"))


def object_map(data):
    indices = {c["header"]: i for i, c in enumerate(data["columns"], 1)}
    pages = {}
    for i, figure in enumerate(data["figures"], 1):
        curves = {}
        plot = 1
        for curve in figure["curves"]:
            binding = dict(plot=plot, sample=curve["sample"], x_column=indices[curve["x"]],
                           y_column=indices[curve["y"]], rows=curve["rows"][:])
            plot += 1
            if "y_error" in curve:
                binding.update(error_plot=plot, y_error_column=indices[curve["y_error"]["column"]])
                plot += 1
            curves[curve["id"]] = binding
        pages[figure["id"]] = dict(page=f"M4Fig{i}", layer=1, curves=curves)
    return dict(workbook="M4Data", worksheet="Raw", figures=pages)


def load_bytes(path, limit):
    path = local_path(path)
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

    try:
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode), f"需要普通文件：{path}")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            require(identity(before) == identity(opened), f"打开时文件已替换：{path}")
            raw = stream.read(limit + 1)
            if len(raw) <= limit:
                require(len(raw) == opened.st_size and identity(opened) == identity(os.fstat(stream.fileno()))
                        == identity(local_path(path).lstat()), f"读取期间文件已变更：{path}")
    except OSError as exc:
        raise InputError("READ_FILE", str(path), str(exc)) from exc
    if len(raw) > limit:
        raise InputError("SIZE_LIMIT", str(path), f"文件超过 {limit} 字节。")
    return raw


def parse_json(raw, field):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError("DUPLICATE_KEY", field, f"JSON 字段重复：{key!r}")
            result[key] = value
        return result

    def invalid(token):
        raise InputError("JSON_NUMBER", field, f"JSON 数值无效：{token}")

    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError("JSON_FORMAT", field, str(exc)) from exc
    except ValueError as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("JSON_FORMAT", field, str(exc)) from exc


def read_json(path):
    return parse_json(load_bytes(path, 256 * 1024), str(path))


def fields(value, path, required, optional=()):
    if not isinstance(value, dict):
        raise InputError("OBJECT", path, "需要一个 JSON 对象。")
    unknown = value.keys() - set(required) - set(optional)
    if unknown:
        raise InputError("UNSUPPORTED_FIELD", path, f"不支持字段 {sorted(unknown)!r}。")
    missing = set(required) - value.keys()
    if missing:
        raise InputError("MISSING_FIELD", path, f"缺少字段 {sorted(missing)!r}。")


def text_value(value, path):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or len(value) > 128 or any(unicodedata.category(c) in {"Cc", "Cs", "Cf", "Zl", "Zp"} for c in value)):
        raise InputError("TEXT", path, "请使用 1–128 字符的单行文字，去掉首尾空格和控制字符。")
    return value
