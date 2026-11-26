"""Wire the public CLI only to offline compilation, verified drafts and appearance."""

import re

from .appearance import apply_appearance
from .common import digest, parse_json
from .csv_task import compile_csv, describe_headers
from .drafts import MANAGED, encoded, read_draft, save_draft, science_digest
from .environment import doctor, resolve_environment, supported_interpreter
from .error_definition import validate_error
from .paths import local_path, require
from .personal_styles import _builtin, capture_profile, list_presets, preset_history, save_preset
from .planner import compile_inputs, inspect_csv
from .summary import preview


def inspect(source):
    require(source.is_file() and source.suffix.casefold() == ".csv", "请选择本次 UTF-8 CSV 文件。")
    info = inspect_csv(source)
    return {**info, "columns": describe_headers(info["headers"])}


def compile_source(source, args, library):
    require(args.data_kind and args.x and args.y, "请明确数据类别、X 列及每个 Y 列。")
    require(args.error_format == "absolute-half-width" and args.y_error,
            "请确认误差为与 Y 同单位的对称绝对半宽，并给出原始材料中的定义。")
    expected = args.expected_sha256
    if expected is None:
        expected = inspect(source)["sha256"]
    else:
        require(re.fullmatch(r"[a-fA-F0-9]{64}", expected), "请提供 inspect 得到的 64 位 SHA-256。")
    errors, columns = {}, {}
    for y, key, definition in args.y_error:
        require(y not in errors, f"响应列 {y!r} 重复指定了误差。")
        validate_error(key, definition)
        errors[y] = dict(column=key, definition=definition)
    for key, quantity, unit in args.column or ():
        require(key not in columns, f"列 {key!r} 重复指定了物理量或单位。")
        columns[key] = dict(quantity=quantity, unit=unit)

    appearance = {}
    def style_task(task):
        profile, defaults = apply_appearance(task, args, library=library)
        appearance.update(source=profile, defaults=defaults)
    compiled = compile_csv(source, data_kind=args.data_kind, title=args.title, kind=args.kind or "scatter",
                           columns=columns, x_header=args.x, y_headers=args.y, y_errors=errors,
                           group_by=args.group_by, branch_by=args.branch_by, sample_names=args.sample,
                           expected_sha256=expected.lower(), task_transform=style_task)
    return compiled, capture_profile(compiled.plan, **appearance)


def restyle(env, folder, args):
    selection = ("data_kind", "x", "y", "y_error", "error_format", "column", "group_by", "branch_by",
                 "sample", "expected_sha256")
    require(all(getattr(args, key) is None for key in selection),
            "更换数据、列、误差定义或单位时，请从原 CSV 新建草稿。")
    source, prior, snapshot = read_draft(env, folder)
    task = parse_json(prior.task_bytes, "task")
    profile, defaults = apply_appearance(task, args, previous=prior.plan, snapshot=snapshot, library=env.library)
    compiled = compile_inputs(encoded(task), lambda name: prior.csv_bytes)
    require(science_digest(compiled.plan) == science_digest(prior.plan), "仅外观调整不得更改源行、物理量或误差绑定。")
    return source, compiled, capture_profile(compiled.plan, source=profile, defaults=defaults)


def summary(folder, source, plan):
    return dict(status="OFFLINE_PREVIEW", native_execution="NOT_EXECUTED",
                native_parent_auto_follow="NOT_EVALUATED", series_visibility_mode=MANAGED,
                draft=str(folder), previews=[str(folder / "preview-1.png")], source=str(source),
                source_sha256=plan["data"]["source_sha256"], plan_digest=digest(plan),
                science_digest=science_digest(plan), style_name=plan["style_name"],
                summary=preview(plan))


def run(args):
    env = resolve_environment(args.config, args.state_dir)
    if args.action == "doctor":
        return doctor(env)
    require(supported_interpreter(), "Use Windows x64 CPython 3.12 for this Alpha. Run doctor for details.")
    if args.action == "presets":
        return {"presets": list_presets(library=env.library)}
    if args.action == "history":
        return {"versions": preset_history(args.name, library=env.library)}
    source = local_path(args.source)
    if args.action == "inspect":
        return inspect(source)
    if args.action == "draft":
        diagnosis = doctor(env)
        require(not diagnosis["issues"], "\n".join(diagnosis["issues"]))
        if args.preset:
            args.preset = _builtin(args.preset) or args.preset
        if source.is_dir():
            source, compiled, style = restyle(env, source, args)
        else:
            require(source.is_file() and source.suffix.casefold() == ".csv", "请选择 UTF-8 CSV 或已验证草稿目录。")
            compiled, style = compile_source(source, args, env.library)
        folder = save_draft(env, source, compiled, style)
        return summary(folder, source, compiled.plan)
    folder = source
    source, compiled, style = read_draft(env, folder)
    if args.action == "preview":
        return summary(folder, source, compiled.plan)
    save_preset(args.name, compiled.plan, library=env.library, snapshot=style, update_from=args.update_from)
    scope, name = (args.name.split("/", 1) if args.name.startswith(("个人/", "实验室/")) else ("个人", args.name))
    version = (args.update_from or 0) + 1
    return {"status": "STYLE_SAVED", "selector": f"{scope}#{version}/{name}", "version": version}

