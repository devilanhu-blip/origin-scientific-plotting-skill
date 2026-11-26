"""Create-only offline drafts and verified replays from the original CSV."""

import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from uuid import uuid4

from .common import digest, fields, load_bytes, parse_json, read_json, sha256
from .paths import local_path, require
from .planner import CSV_LIMIT, compile_inputs
from .science_check import check_science
from .sketch import write_previews
from .styles import _load_preset

SCHEMA = "origin-alpha.offline-draft/1"
MANAGED = "SKILL_MANAGED_SERIES_VISIBILITY"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def science_digest(plan):
    data = plan["data"]
    figures = []
    for figure in data["figures"]:
        curves = [{k: v for k, v in c.items() if k not in {"label", "kind"}} for c in figure["curves"]]
        figures.append(dict(id=figure["id"], axes=figure["axes"], curves=curves))
    return digest({**data, "figures": figures, "excluded_csv_headers": plan["excluded_csv_headers"]})


def confirmed_scope(compiled):
    from .error_definition import validate_error

    plan = compiled.plan
    require(isinstance(plan.get("style_name"), str), "草稿需要具名风格，请从 CSV 创建公开草稿。")
    figures = plan["data"]["figures"]
    require(len(figures) == 1 and len(figures[0]["curves"]) == 2,
            "当前公开范围需要一张图、两条各自具有同单位对称绝对 Y 半宽的曲线。")
    bound = set()
    for curve in figures[0]["curves"]:
        require("y_error" in curve, "两条曲线都需要明确绑定 Y 误差列。")
        error = curve["y_error"]
        validate_error(error["column"], error["definition"])
        bound.add((error["column"], tuple(curve["rows"])))
    require(len(bound) == 2, "两条曲线引用同一误差列的同一行区间，无法区分对应的误差对象。")
    task = parse_json(compiled.task_bytes, "task")
    require(task.get("csv_sha256") == sha256(compiled.csv_bytes), "任务必须绑定已核对的原始 CSV 摘要。")
    require("pdf_fonts" not in task, "本公开候选只生成离线 PNG 预览。")
    preset, _ = _load_preset(plan["styles"]["preset"])
    check_science(task, compiled, preset)


def _file_hash(path):
    with local_path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save_draft(env, source, compiled, style):
    confirmed_scope(compiled)
    parent = local_path(env.state / "drafts")
    parent.mkdir(exist_ok=True, parents=True)
    dest = local_path(parent / ("plot-" + uuid4().hex))
    with TemporaryDirectory(prefix=".preparing-", dir=parent) as temp:
        staged = Path(temp) / "draft"
        staged.mkdir()
        (staged / "task.json").write_bytes(compiled.task_bytes)
        (staged / "style.json").write_bytes(encoded(style))
        (staged / "plan.json").write_bytes(encoded(compiled.plan))
        images = write_previews(compiled.plan, staged, (env.regular, env.bold))
        record = dict(schema=SCHEMA, source=str(source), plan_digest=digest(compiled.plan),
                      style_digest=digest(style), images={p.name: _file_hash(p) for p in images})
        (staged / "draft.json").write_bytes(encoded(record))
        require(sha256(load_bytes(source, CSV_LIMIT)) == compiled.plan["data"]["source_sha256"],
                "生成预览期间 CSV 已改变，请重新核对。")
        staged.rename(dest)
    return dest


def read_draft(env, path):
    folder = local_path(path)
    require(folder.parent == local_path(env.state / "drafts") and re.fullmatch(r"plot-[0-9a-f]{32}", folder.name),
            "草稿须来自本次所选状态目录；使用相同的 --state-dir 或 --config。")
    meta = read_json(folder / "draft.json")
    fields(meta, "draft", ("schema", "source", "plan_digest", "style_digest", "images"))
    require(meta["schema"] == SCHEMA, "草稿版本不匹配，请从原始 CSV 创建新草稿。")
    source = local_path(meta["source"])
    task = load_bytes(folder / "task.json", 256 * 1024)
    def read_csv(name):
        require(source.name == name, "草稿的 CSV 名称与原始来源不一致。")
        return load_bytes(source, CSV_LIMIT)
    compiled = compile_inputs(task, read_csv)
    confirmed_scope(compiled)
    plan = compiled.plan
    require(digest(plan) == meta["plan_digest"] and _file_hash(folder / "plan.json") == sha256(encoded(plan)),
            "保存的计划、任务或内置样式已改变，请从原始材料重新预览。")
    style = read_json(folder / "style.json")
    require(digest(style) == meta["style_digest"], "保存的风格快照已改变，请从原始材料重新预览。")
    require(meta["images"] == {"preview-1.png": _file_hash(folder / "preview-1.png")},
            "草图已被修改，请从原始材料重新预览。")
    return source, compiled, style

