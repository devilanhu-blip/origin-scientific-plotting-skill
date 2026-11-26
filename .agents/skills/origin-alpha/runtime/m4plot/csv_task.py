"""Translate unambiguous CSV headings or Codex's explicit XY selection to one ordinary task."""

import json
from pathlib import Path

from .common import InputError, fields, load_bytes, sha256
from .csv_groups import branch_ranges, group_ranges
from .planner import CSV_LIMIT, IDENTIFIER, compile_inputs, csv_filename, error_binding, records
from .science_headers import (COMMON_UNITS, KNOWN_UNITS, canonical_quantity, canonical_unit,
                              classify, describe_headers, temperature_role)


def _names(values, field):
    if values is None:
        return []
    if (not isinstance(values, (list, tuple)) or not values
            or any(not isinstance(v, str) or not v.strip() for v in values)
            or len(set(values)) != len(values)):
        raise InputError("XY_SELECTION", field, "请提供不重复的列名或样品名称。")
    return list(values)


def _infer_curves(parts, *, x_header, y_headers, quantity, sample_names):
    ys = _names(y_headers, "y_headers")
    samples = _names(sample_names, "sample_names")
    if quantity is not None and (not isinstance(quantity, str) or not quantity.strip()):
        raise InputError("XY_SELECTION", "quantity", "请指定要绘制的物理量。")
    explicit_headers = ys if x_header is None else [x_header, *ys]
    for h in explicit_headers:
        if not isinstance(h, str) or h not in parts:
            raise InputError("COLUMN_MISSING", "curves", f"CSV 中没有表头 {h!r}。")
    groups = [h for h, info in parts.items() if info.role == "group"]
    if groups:
        raise InputError("XY_SELECTION", "curves",
                         f"列 {groups!r} 可能按行区分样品。若同一样品的行连续，请指定按哪一列分组。")

    requested_quantity = canonical_quantity(quantity) if quantity is not None else None
    temp_role = temperature_role(parts)
    # If the request targets temperature explicitly, a time series with another
    # measured property can still select temperature as its response.
    temp_y = temp_role == "y" or requested_quantity == "温度"
    responses = [h for h, info in parts.items()
                 if info.role == "y" or (info.role == "temperature" and temp_y)]
    requested = bool(ys or requested_quantity or samples)
    if not requested:
        unknown = [h for h, info in parts.items() if info.role == "unknown" and h != x_header]
        if unknown:
            raise InputError("XY_SELECTION", "curves", f"请指定要绘制的 Y 列或物理量。待辨认列为 {unknown!r}。")
    if ys:
        if requested_quantity and any(parts[h].quantity != requested_quantity for h in ys):
            raise InputError("XY_SELECTION", "quantity", "所选 Y 列与指定物理量不一致，请核对列名。")
        if samples and {parts[h].sample for h in ys} != set(samples):
            raise InputError("XY_SELECTION", "sample_names", "所选 Y 列与指定样品不一致，请核对样品名。")
    else:
        ys = [h for h in responses if (not requested_quantity or parts[h].quantity == requested_quantity)
              and (not samples or parts[h].sample in samples) and h != x_header]
        missing = [name for name in samples if not any(parts[h].sample == name for h in ys)]
        if missing:
            raise InputError("XY_SELECTION", "sample_names", f"在所选物理量中找不到样品 {missing!r}。")
    if not ys:
        options = list(dict.fromkeys(parts[h].quantity for h in responses))
        raise InputError("XY_SELECTION", "curves", f"没有选中 Y 列。可辨认的响应量为 {options!r}，也可指定准确表头。")
    quantities = list(dict.fromkeys((parts[h].quantity, parts[h].unit) for h in ys))
    if len(quantities) > 1 and all(parts[h].role != "unknown" and parts[h].unit for h in ys):
        options = "、".join(f"{name} [{unit}]" for name, unit in quantities)
        raise InputError("AXIS_MISMATCH", "curves",
                         f"表中包含 {options}。请选择同一物理量和单位的 Y 列，或分开作图。")
    if len(ys) > 3:
        raise InputError("COUNT", "curves", f"同图最多三条曲线。请在 {ys!r} 中指定要比较的样品或 Y 列。")
    if x_header is not None:
        if x_header in ys:
            raise InputError("XY_IDENTICAL", "x_header", "X 列也被选作 Y，请重新指定。")
        return [dict(x=x_header, y=h) for h in ys]
    x_headers = [h for h, info in parts.items() if h not in ys and
                 (info.role == "x" or (info.role == "temperature" and not temp_y))]
    curves = []
    for y in ys:
        sample = parts[y].sample
        matches = [h for h in x_headers if not parts[h].sample or parts[h].sample == sample]
        if len(matches) != 1:
            raise InputError("XY_SELECTION", "curves",
                             f"{y!r} 需要一个明确的 X 列，可配对的表头为 {matches!r}。请指定横坐标。")
        curves.append(dict(x=matches[0], y=y))
    if not requested and {c["x"] for c in curves} != set(x_headers):
        raise InputError("XY_SELECTION", "curves", "部分 X 列没有对应的数据系列，请确认使用哪几列。")
    return curves


def _default_sample(label):
    if IDENTIFIER.fullmatch(label):
        return label
    return "Sample_" + sha256(label.encode("utf-8"))[:16]


def _grouped_series(raw, parts, group_by, branch_by, sample_names):
    if not isinstance(group_by, str) or group_by not in parts:
        raise InputError("COLUMN_MISSING", "group_by", f"CSV 中没有分组列 {group_by!r}。")
    if parts[group_by].role not in {"group", "unknown"}:
        raise InputError("GROUP_COLUMN", "group_by", "请指定记录样品名称的分组列。")
    ranges = group_ranges(raw, group_by, _names(sample_names, "sample_names"))
    grouping = {"column": group_by, "samples": {_default_sample(name): name for name in ranges}}
    if len(grouping["samples"]) != len(ranges):
        raise InputError("GROUP_SAMPLES", group_by, "样品的内部标识重合，请明确区分材料名称。")
    if branch_by is None:
        return [dict(sample=_default_sample(name), label=name, rows=bounds) for name, bounds in ranges.items()], grouping
    if branch_by not in parts or parts[branch_by].role not in {"unknown", "auxiliary"} or parts[branch_by].unit:
        raise InputError("BRANCH_COLUMN", "branch_by", "请指定原表中记录过程或阶段名称的标签列。")
    grouping["branch_column"] = branch_by
    intervals = branch_ranges(raw, group_by, branch_by, ranges)
    series = [dict(sample=_default_sample(name), segment=phase, label=f"{name} · {phase}", rows=bounds)
              for name, branches in intervals.items() for phase, bounds in branches.items()]
    return series, grouping


def _column_spec(header, inferred, metadata):
    if header in metadata:
        spec = metadata[header]
    elif inferred.unit:
        spec = {"quantity": inferred.quantity, "unit": inferred.unit}
    else:
        raise InputError("UNIT_UNKNOWN", header, "请从材料确定该列物理量与单位，无量纲量可明确填 1。")
    fields(spec, header, ["quantity", "unit"])
    quantity, unit = inferred.quantity, inferred.unit
    declared = spec["quantity"]
    if quantity in COMMON_UNITS and isinstance(declared, str):
        declared_quantity = canonical_quantity(declared)
        if declared_quantity in COMMON_UNITS and declared_quantity != quantity:
            raise InputError("QUANTITY_MISMATCH", header, "指定物理量与表头含义冲突。")
    if unit and quantity in COMMON_UNITS and unit not in COMMON_UNITS[quantity]:
        if unit in KNOWN_UNITS:
            raise InputError("UNIT_MISMATCH", header, "表头的物理量与单位不相符，请核对材料。")
        if header not in metadata:
            raise InputError("UNIT_UNKNOWN", header, "此单位需要根据材料明确指定。")
    if unit and isinstance(spec["unit"], str) and canonical_unit(spec["unit"]) != unit:
        raise InputError("UNIT_MISMATCH", header, "指定单位与列名中的单位冲突，请核实原始材料。")
    if not unit and quantity in COMMON_UNITS and isinstance(spec["unit"], str):
        supplied = canonical_unit(spec["unit"])
        if supplied in KNOWN_UNITS and supplied not in COMMON_UNITS[quantity]:
            raise InputError("UNIT_MISMATCH", header, "补充的单位与表头物理量不相符，请核对材料。")
    return spec


def compile_csv(path, *, data_kind, preset="clean", title=None, kind="scatter", curves=None,
                columns=None, defaults=None, samples=None, expected_sha256=None,
                x_header=None, y_headers=None, quantity=None, sample_names=None, group_by=None, branch_by=None,
                page_quantities=None, page_titles=None, task_transform=None, y_errors=None):
    """Return a Compilation using the same checked bytes for inference, plotting and receipt.

    curves is an ordered list of {x, y, optional sample, label, kind, rows, id, y_error}.
    y_errors maps exact Y headers to explicit {column, definition} bindings for all
    their plotted intervals. No error values or uncertainty definitions are inferred.
    x_header is an explicit shared X. y_headers is an ordered selection; quantity and
    sample_names select matching responses. group_by binds one contiguous row interval
    per selected category to a shared XY pair. task_transform can customize the assembled
    task before the normal compiler validates the full data and style contract.
    columns supplies missing {quantity, unit} by exact header. The existing task
    compiler validates a common axis per figure, row intervals and all style fields.
    """
    path = Path(path)
    name = csv_filename(path.name)
    raw = load_bytes(path, CSV_LIMIT)
    source_hash = sha256(raw)
    if expected_sha256 is not None and expected_sha256 != source_hash:
        raise InputError("SOURCE_CHANGED", "expected_sha256", "CSV 已改变，请重新核对表头、单位和映射。")
    headers = next(records(raw))
    parts = {h: classify(h) for h in headers}
    if curves is not None and any(v is not None for v in
                                  (x_header, y_headers, quantity, sample_names, group_by, branch_by, page_quantities)):
        raise InputError("XY_SELECTION", "curves", "已有逐条 XY 映射，请只保留一种列选择方式。")
    if branch_by is not None and group_by is None:
        raise InputError("BRANCH_COLUMN", "group_by", "分段图须同时指定原始样品列与阶段列。")
    if page_quantities is None:
        if page_titles is not None:
            raise InputError("PAGE_TITLE", "page_titles", "分别指定页标题时，请先为两张图分别选定响应量。")
        quantities = [quantity]
        titles = [path.stem if title is None else title]
    else:
        quantities = [canonical_quantity(s) for s in _names(page_quantities, "page_quantities")]
        if len(quantities) != 2 or len(set(quantities)) != 2 or y_headers is not None or quantity is not None:
            raise InputError("PAGE_QUANTITIES", "page_quantities", "分图请指定两个不同的响应量，勿同时选择单图的 Y 列或物理量。")
        if title is not None or (page_titles is not None and
                                (not isinstance(page_titles, (list, tuple)) or len(page_titles) != len(quantities))):
            raise InputError("PAGE_TITLE", "page_titles", "双图可按响应量顺序分别指定两个标题，或沿用各物理量名称。")
        titles = quantities if page_titles is None else page_titles
    metadata = {} if columns is None else columns
    if not isinstance(metadata, dict):
        raise InputError("OBJECT", "columns", "按表头提供物理量与单位。")

    if y_errors is None:
        y_errors = {}
    if not isinstance(y_errors, dict):
        raise InputError("ERROR_COLUMN", "y_errors", "按准确 Y 表头分别指定误差列与含义。")
    error_sources = set()
    for y, spec in y_errors.items():
        binding = error_binding(spec, f"y_errors[{y!r}]")
        if y not in parts or binding["column"] not in parts:
            raise InputError("COLUMN_MISSING", "y_errors", f"请核对 Y 表头 {y!r} 与误差列表头 {binding['column']!r}。")
        error_sources.add(binding["column"])
    mapped_y = set()

    selected = {}
    grouping = None
    series = None
    if group_by is not None:
        series, grouping = _grouped_series(raw, parts, group_by, branch_by, sample_names)
    numeric_parts = {h: info for h, info in parts.items() if h not in (group_by, branch_by) and h not in error_sources}
    figures = []
    next_id = 1
    for page, (response, heading) in enumerate(zip(quantities, titles, strict=True), 1):
        page_curves = curves
        if page_curves is None:
            page_curves = _infer_curves(numeric_parts, x_header=x_header, y_headers=y_headers,
                                        quantity=response, sample_names=None if grouping else sample_names)
            if page_quantities is not None and not grouping and any(not parts[c["y"]].sample for c in page_curves):
                raise InputError("PAGE_SAMPLE", "page_quantities",
                                 "双指标宽表的响应列缺少样品名，无法确认跨页样品身份。请提供各列对应的真实样品名用于明确任务映射，或按原表样品列分组。")
            if grouping:
                if len(page_curves) != 1 or any(parts[h].sample for h in page_curves[0].values()):
                    raise InputError("XY_SELECTION", "group_by", "请为每张样品分组图指定一组共享的 X、Y 数值列。")
                page_curves = [{**page_curves[0], **member} for member in series]
        if not isinstance(page_curves, list) or not 1 <= len(page_curves) <= 3:
            raise InputError("COUNT", "curves", "一张图支持一至三条曲线，分段图可按样品名缩小选择范围。")
        configured = []
        for curve in page_curves:
            field = f"figures[{page}].curves[{len(configured) + 1}]"
            fields(curve, field, ["x", "y"], ["sample", "label", "id", "kind", "rows", "segment", "y_error"])
            for axis in ("x", "y"):
                h = curve[axis]
                if not isinstance(h, str) or h not in parts:
                    raise InputError("COLUMN_MISSING", field + "." + axis, f"CSV 中没有表头 {h!r}。")
                selected[h] = _column_spec(h, parts[h], metadata)
            y = curve["y"]
            if y in y_errors:
                if "y_error" in curve:
                    raise InputError("ERROR_COLUMN", field, "请为该曲线只选择一种误差列绑定方式。")
                curve = {**curve, "y_error": y_errors[y]}
                mapped_y.add(y)
            if "y_error" in curve:
                binding = error_binding(curve["y_error"], field + ".y_error")
                error = binding["column"]
                if error not in parts:
                    raise InputError("COLUMN_MISSING", field + ".y_error", f"CSV 中没有误差列 {error!r}。")
                selected[error] = _column_spec(error, parts[error], metadata)
            identity = parts[y].sample or y
            configured.append({"id": f"Curve{next_id}", "sample": _default_sample(identity),
                               "label": identity, "kind": kind, **curve})
            next_id += 1
        figures.append(dict(id=f"Figure{page}", title=heading, curves=configured))
    if page_quantities is not None and not grouping:
        compared = [{c["sample"] for c in f["curves"]} for f in figures]
        if compared[0] != compared[1]:
            raise InputError("PAGE_SAMPLE", "page_quantities",
                             "两个响应量包含的样品不同。请点名两页都要比较的样品，或明确各页样品分别建图。")
    if set(y_errors) != mapped_y:
        raise InputError("ERROR_COLUMN", "y_errors", f"已配置误差的 Y 列没有绘入本图：{sorted(set(y_errors) - mapped_y)!r}。")
    unused = set(metadata) - set(selected)
    if unused:
        raise InputError("COLUMN_UNUSED", "columns", f"给出了未绑定列的物理量：{sorted(unused)!r}。")
    style = {"preset": preset}
    if defaults is not None:
        style["defaults"] = defaults
    if samples is not None:
        style["samples"] = samples
    schema = "m4-mvp1.task/2" if branch_by is not None or page_quantities is not None else "m4-mvp1.task/1"
    if any("y_error" in c for fig in figures for c in fig["curves"]):
        schema = "m4-mvp1.task/3"
    task = dict(schema=schema, data_kind=data_kind, csv=name, csv_sha256=source_hash,
                columns=selected, figures=figures, style=style)
    if grouping:
        task["grouping"] = grouping
    if task_transform is not None:
        task_transform(task)
    task_raw = (json.dumps(task, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    return compile_inputs(task_raw, lambda _: raw)
