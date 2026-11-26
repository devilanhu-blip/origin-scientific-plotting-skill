"""Compile an explicit task against one immutable byte snapshot of a wide CSV."""

import io
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath

from .common import InputError, digest, fields, load_bytes, object_map, parse_json, sha256, text_value
from .legend_layout import check_position
from .science_headers import canonical_unit, classify, error_unit_scale, explicitly_relative
from .styles import resolve_style


CSV_LIMIT = 16 * 1024 * 1024
CSV_FIELD_LIMIT = 131_072
MAX_RECORDS = 100_000
ORIGIN_MISSING_VALUE = -1.23456789e-300
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
KINDS = {"scatter", "line", "linesymbol"}
TASK_SCHEMAS = ("m4-mvp1.task/1", "m4-mvp1.task/2", "m4-mvp1.task/3")
# Original bytes of the published SIMULATED examples, including renamed copies.
SIMULATED_EXAMPLE_HASHES = {
    "c51448b1c1546a66db958e0404e42d17e6e2000b60a605583aac65c001cd1ad2",
    "2ae0fb4538f4da2fbf575c979eb0d3492d3be6b1dd80d0a3dc8a6d68ba30a662",
    "955d865bb81eb2f06cd68d307e9c9c0a505c03b48b3cfa59c4dd1b3525032645",
    "3dcbce9696804c3b8b1b6915691c17915092c23acf1d3649ba412e0d8360d4e3",
    "7095a6201e94e06ba39829dd0f90904f10e4deadda8567d15b7a61c64dc9e316",
    "c5e0e6ff03ad511c2c391668db9d1115d520013de1099f1ce5a1304a66f037fe",
    "c7684aab205d6bcaabd33616a941d205c492cd878cd2c5a2fd2aab1cd030799c",
    "efb5a4a89be86295edcd5531f63788357449720fa64eae966d9271415f6cf404",
}


@dataclass(frozen=True)
class Compilation:
    plan: dict
    task_bytes: bytes
    csv_bytes: bytes


def identifier(value, path):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise InputError("ID", path, "标识符须以英文字母开始，仅限字母、数字、下划线，最长 32 字符。")
    return value


def csv_filename(value):
    text_value(value, "csv")
    path = PureWindowsPath(value)
    if (path.name != value or path.suffix.lower() != ".csv" or path.is_reserved()
            or any(c in value for c in '<>:"/\\|?*')):
        raise InputError("CSV_NAME", "csv", "须填写与任务文件同目录的 CSV 文件名。")
    return value


def _check_csv_field_size(length, location):
    if length > CSV_FIELD_LIMIT:
        raise InputError("CSV_FIELD_LIMIT", location, f"单元格最多 {CSV_FIELD_LIMIT} 个 Unicode 字符。")


def _quoted_csv_field(line, start, location):
    cursor, length = start + 1, 0
    while True:
        quote = line.find('"', cursor)
        if quote == -1:
            raise InputError("CSV_FORMAT", location, "引号未闭合。CSV 单元格不能跨行。")
        length += quote - cursor
        trailing = line[quote + 1:quote + 2]
        if trailing != '"':
            _check_csv_field_size(length, location)
            if trailing not in ("", ","):
                raise InputError("CSV_FORMAT", location, "闭合引号后须为逗号或行尾。")
            return line[start + 1:quote].replace('""', '"'), quote + 1
        length += 1
        _check_csv_field_size(length, location)
        cursor = quote + 2


def _csv_record(line, location, column_limit):
    # Single-line CSV with explicit field limits, independent of csv.field_size_limit().
    line = line.removesuffix("\n").removesuffix("\r")
    if not line:
        return []
    row = []
    start = 0
    while True:
        if len(row) == column_limit:
            code = "CSV_HEADER" if location == "csv.header" else "CSV_ROW"
            raise InputError(code, location, f"列数超过 {column_limit}。")
        field = f"{location}[{len(row) + 1}]"
        if line[start:start + 1] == '"':
            token, end = _quoted_csv_field(line, start, field)
        else:
            comma = line.find(",", start)
            end = len(line) if comma == -1 else comma
            _check_csv_field_size(end - start, field)
            token = line[start:end]
        row.append(token)
        if end == len(line):
            return row
        start = end + 1


def records(raw):
    try:
        reader = io.StringIO(raw.decode("utf-8-sig"), newline="")
    except UnicodeDecodeError as exc:
        raise InputError("CSV_FORMAT", "csv", str(exc)) from exc
    headers = _csv_record(next(reader, ""), "csv.header", 128)
    if not headers:
        raise InputError("CSV_HEADER", "csv", "CSV 缺少表头。")
    if len(set(headers)) != len(headers):
        raise InputError("CSV_HEADER", "csv", "需要 1–128 个唯一表头，重名列须先区分。")
    for idx, header in enumerate(headers, 1):
        text_value(header, f"csv.header[{idx}]")
    yield headers
    count = 0
    for count, line in enumerate(reader, 1):
        if count > MAX_RECORDS:
            raise InputError("ROW_LIMIT", "csv", f"单份 CSV 最多 {MAX_RECORDS} 个数据行。")
        location = f"csv.data[{count}]"
        row = _csv_record(line, location, len(headers))
        if len(row) != len(headers):
            raise InputError("CSV_ROW", location, "列数与表头不符。")
        yield row
    if count == 0:
        raise InputError("NO_DATA", "csv", "至少需要一个数据行。")


def inspect_csv(path):
    """Return exact column names and a raw three-record preview for task authoring."""
    path = Path(path)
    raw = load_bytes(path, CSV_LIMIT)
    it = records(raw)
    headers = next(it)
    preview = []
    for count, row in enumerate(it, 1):
        if count <= 3:
            preview.append(row)
    return dict(file=path.name, sha256=sha256(raw), headers=headers, row_count=count, preview=preview)


def numeric(token, field):
    stripped = token.strip()
    if not NUMBER.fullmatch(stripped):
        raise InputError("NUMBER", field, f"需要有限十进制数，实际为 {token[:80]!r}。")
    try:
        value = float(stripped)
        if value == ORIGIN_MISSING_VALUE:
            raise InputError("ORIGIN_MISSING_VALUE", field, "该数值为 Origin 保留的缺测标记。")
        # Preserve every significant input digit at the decimal -> double -> decimal boundary.
        precise = Decimal(stripped)
        if not math.isfinite(value) or precise != Decimal(str(value)):
            raise InputError("NUMBER_PRECISION", field, "Origin 双精度值不能往返保留该十进制读数。")
    except (InvalidOperation, OverflowError) as exc:
        raise InputError("NUMBER_PRECISION", field, "数值超出支持范围。") from exc
    return value


def plain_label(value, path):
    value = text_value(value, path)
    if any(marker in value for marker in ("\\", "%(", "$(", "%[", "%$", "%@")) or re.search(r"%[A-Za-z]", value):
        raise InputError("RICH_TEXT", path, "仅接受纯文字，数学符号可直接使用 Unicode。")
    return value


def data_columns(raw, spec):
    if not isinstance(spec, dict) or len(spec) < 2:
        raise InputError("COLUMNS", "columns", "至少声明两个不同的数值列及其物理量、单位。")
    it = records(raw)
    headers = next(it)
    missing = set(spec) - set(headers)
    if missing:
        raise InputError("COLUMN_MISSING", "columns", f"CSV 中缺少列 {sorted(missing)!r}。")
    selected = []
    for index, header in enumerate(headers):
        if header not in spec:
            continue
        info = spec[header]
        field = f"columns[{header!r}]"
        fields(info, field, ["quantity", "unit"])
        plain_label(header, field)
        quantity = plain_label(info["quantity"], field + ".quantity")
        unit = plain_label(info["unit"], field + ".unit")
        if unit.casefold() in {"unknown", "?", "未知", "待定", "n/a"}:
            raise InputError("UNIT_UNKNOWN", field + ".unit", "请填写已知单位；无量纲填 1。")
        selected.append((index, dict(header=header, quantity=quantity, unit=unit, values=[], tokens=[])))
    for row_no, row in enumerate(it, 1):
        for index, col in selected:
            token = row[index]
            col["values"].append(numeric(token, f"csv.data[{row_no}][{col['header']!r}]"))
            col["tokens"].append(token)
    return [col for _, col in selected], [name for name in headers if name not in spec]


def bounded_list(value, minimum, maximum, field):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise InputError("COUNT", field, f"项目数须在 {minimum}–{maximum} 之间。")


def error_binding(spec, location):
    """One explicit, absolute, symmetric Y half-width from the same CSV record."""
    fields(spec, location, ["column", "definition"])
    header = plain_label(spec["column"], location + ".column")
    definition = plain_label(spec["definition"], location + ".definition")
    if definition.casefold() in {"?", "n/a", "unknown", "tbd", "未知", "不详", "待定", "待确认",
                                 "error", "误差", "误差棒", "uncertainty", "不确定度"}:
        raise InputError("ERROR_DEFINITION", location, "请填写材料给出的误差棒含义，例如样本标准差或仪器规定的绝对误差。")
    return {"column": header, "definition": definition}


def normalize_figures(spec, columns, count, *, task_v2=False, task_v3=False):
    bounded_list(spec, 1, 2, "figures")
    catalog = {col["header"]: {"quantity": col["quantity"], "unit": col["unit"]} for col in columns}
    values = {col["header"]: col["values"] for col in columns}
    xy_headers, error_definitions = set(), {}
    graph_ids, curve_ids, used = set(), set(), set()
    figures = []
    for index, obj in enumerate(spec):
        field = f"figures[{index}]"
        fields(obj, field, ["id", "title", "curves"], ["legend_position"])
        graph_id = identifier(obj["id"], field + ".id")
        if graph_id in graph_ids:
            raise InputError("ID_DUPLICATE", field + ".id", graph_id)
        graph_ids.add(graph_id)
        title = plain_label(obj["title"], field + ".title")
        bounded_list(obj["curves"], 1, 3, field + ".curves")
        axes, curves, legends = {}, [], set()
        for pos, item in enumerate(obj["curves"]):
            loc = f"{field}.curves[{pos}]"
            optional = ["rows", "segment"] if task_v2 else ["rows"]
            if task_v3:
                optional.append("y_error")
            fields(item, loc, ["id", "sample", "label", "x", "y", "kind"], optional)
            cid = identifier(item["id"], loc + ".id")
            if cid in curve_ids:
                raise InputError("ID_DUPLICATE", loc + ".id", cid)
            curve_ids.add(cid)
            sample = identifier(item["sample"], loc + ".sample")
            label = plain_label(item["label"], loc + ".label")
            if label in legends:
                raise InputError("LEGEND_DUPLICATE", loc + ".label", "同一图内请给曲线可区分的图例文字。")
            legends.add(label)
            kind = item["kind"]
            if not isinstance(kind, str) or kind not in KINDS:
                raise InputError("PLOT_KIND", loc + ".kind", "支持 scatter、line、linesymbol。")
            for axis in ("x", "y"):
                col = item[axis]
                if not isinstance(col, str) or col not in catalog:
                    raise InputError("XY_COLUMN", loc + "." + axis, f"{col!r} 未在 columns 中声明。")
                if axes.setdefault(axis, catalog[col]) != catalog[col]:
                    raise InputError("AXIS_MISMATCH", loc + "." + axis, "同一坐标轴上的物理量和单位须完全一致。")
                used.add(col)
                xy_headers.add(col)
            if item["x"] == item["y"]:
                raise InputError("XY_IDENTICAL", loc, "此版本要求 X、Y 绑定不同的源列。")
            rows = item.get("rows", [1, count])
            if (not isinstance(rows, list) or len(rows) != 2 or any(type(i) is not int for i in rows)
                    or not 1 <= rows[0] <= rows[1] <= count):
                raise InputError("ROWS", loc + ".rows", f"数据行从 1 计数，闭区间必须位于 1–{count}。")
            if kind != "scatter" and rows[0] == rows[1]:
                raise InputError("LINE_POINTS", loc + ".rows", "连线至少需要两个数据点。")
            curve = dict(id=cid, sample=sample, label=label, x=item["x"], y=item["y"], kind=kind, rows=rows)
            if "y_error" in item:
                loc_error = loc + ".y_error"
                binding = error_binding(item["y_error"], loc_error)
                header, y_header = binding["column"], item["y"]
                if header not in catalog:
                    raise InputError("ERROR_COLUMN", loc_error, f"误差列 {header!r} 未在 columns 中声明。")
                if explicitly_relative(header, catalog[header]["quantity"], binding["definition"]):
                    raise InputError("ERROR_RELATIVE", loc_error, "该列或定义标示相对误差。请提供与 Y 同量级的绝对误差半宽列。")
                for name in (header, y_header):
                    source_unit = classify(name).unit
                    if source_unit is not None and source_unit != canonical_unit(catalog[name]["unit"]):
                        raise InputError("ERROR_UNIT", loc_error, f"{name!r} 的声明单位与原始表头不符。")
                if error_unit_scale(catalog[header]["unit"]) != canonical_unit(catalog[y_header]["unit"]):
                    raise InputError("ERROR_UNIT", loc_error, "对称绝对误差列须使用与对应 Y 列相同的单位和量级。")
                if header in error_definitions and binding["definition"] != error_definitions[header]:
                    raise InputError("ERROR_DEFINITION", loc_error, f"同一源列 {header!r} 被赋予了不同的误差定义，请核对。")
                if header not in error_definitions:
                    for row_no, width in enumerate(values[header], 1):
                        if width < 0:
                            raise InputError("ERROR_NEGATIVE", f"csv.data[{row_no}][{header!r}]", "绝对误差半宽须大于或等于零。")
                for row_no in range(rows[0] - 1, rows[1]):
                    width, y = values[header][row_no], values[y_header][row_no]
                    if not (math.isfinite(y - width) and math.isfinite(y + width)):
                        raise InputError("ERROR_EXTENT", f"csv.data[{row_no + 1}][{header!r}]", "误差棒端点超出有限数值范围。")
                curve["y_error"] = binding
                error_definitions[header] = binding["definition"]
                used.add(header)
            if "segment" in item:
                curve["segment"] = plain_label(item["segment"], loc + ".segment")
            curves.append(curve)
        figure = dict(id=graph_id, title=title, axes=axes, curves=curves)
        if "legend_position" in obj:
            figure["legend_position"] = check_position(obj["legend_position"], field + ".legend_position")
        figures.append(figure)
    if not task_v2 and len(curve_ids) > 3:
        raise InputError("CURVE_LIMIT", "figures", "一个任务合计最多三条曲线。")
    if xy_headers & error_definitions.keys():
        raise InputError("ERROR_COLUMN", "figures", f"误差列与坐标列重叠：{sorted(xy_headers & error_definitions.keys())!r}。")
    if set(catalog) - used:
        raise InputError("COLUMN_UNUSED", "columns", f"有已声明但未绑定的列：{sorted(set(catalog) - used)!r}。")
    return figures


def compile_snapshot(task_path):
    path = Path(task_path)
    task_raw = load_bytes(path, 256 * 1024)
    return compile_inputs(task_raw, lambda name: load_bytes(path.parent / name, CSV_LIMIT))


def compile_inputs(task_raw, read_csv):
    """Resolve only the validated adjacent filename through the caller's snapshot reader."""
    task = parse_json(task_raw, "task")
    fields(task, "task", ["schema", "data_kind", "csv", "columns", "figures", "style"],
           ["csv_sha256", "style_name", "grouping", "pdf_fonts"])
    if task["schema"] not in TASK_SCHEMAS:
        raise InputError("SCHEMA", "schema", "需要 m4-mvp1.task/1、/2 或 /3。")
    task_v2 = task["schema"] in TASK_SCHEMAS[1:]
    task_v3 = task["schema"] == TASK_SCHEMAS[2]
    if "pdf_fonts" in task and (not task_v3 or task["pdf_fonts"] != "request-embedded"):
        raise InputError("PDF_FONTS", "pdf_fonts", "task/3 可用 request-embedded 请求在原生导出 PDF 时嵌入字体。")
    if task["data_kind"] not in ("MEASURED", "SIMULATED"):
        raise InputError("DATA_KIND", "data_kind", "请显式指定 MEASURED 或 SIMULATED。")
    name = csv_filename(task["csv"])
    raw = read_csv(name)
    source_hash = sha256(raw)
    if "csv_sha256" in task:
        claimed = task["csv_sha256"]
        if not isinstance(claimed, str) or not re.fullmatch("[a-fA-F0-9]{64}", claimed):
            raise InputError("HASH_FORMAT", "csv_sha256", "请填写 CSV 原始文件的 64 位十六进制 SHA-256。")
        if claimed.lower() != source_hash:
            raise InputError("SOURCE_CHANGED", "csv_sha256", f"当前 CSV 的 SHA-256 为 {source_hash}。")
    columns, excluded = data_columns(raw, task["columns"])
    count = len(columns[0]["values"])
    figures = normalize_figures(task["figures"], columns, count, task_v2=task_v2, task_v3=task_v3)
    if "grouping" not in task and any("segment" in c for f in figures for c in f["curves"]):
        raise InputError("BRANCH_COLUMN", "grouping", "曲线阶段需要对应原始样品列和阶段列。")
    if task["data_kind"] == "MEASURED":
        labels = [Path(name).stem, *(figure["title"] for figure in figures)]
        marked = any(re.match(r"^SIMULATED(?:$|[^A-Za-z0-9])", label, re.I) for label in labels)
        if marked or source_hash in SIMULATED_EXAMPLE_HASHES:
            raise InputError("DATA_KIND", "data_kind", "输入含已知模拟数据或模拟标记，请标为 SIMULATED。")
    samples = sorted({curve["sample"] for graph in figures for curve in graph["curves"]})
    styles = resolve_style(task["style"], samples, figures)
    data = dict(kind=task["data_kind"], source_name=name, source_sha256=source_hash, row_count=count,
                columns=columns, figures=figures)
    if "grouping" in task:
        from .csv_groups import validate_grouping
        data["grouping"] = validate_grouping(raw, task["grouping"], figures, task["columns"])
    plan = dict(schema="m4-mvp1.plan/1", status="OFFLINE_PLAN", native_authorized=False,
                native_observed=False, task_sha256=sha256(task_raw), data=data, data_sha256=digest(data),
                styles=styles, style_sha256=digest(styles), object_map=object_map(data), excluded_csv_headers=excluded)
    if "style_name" in task:
        plan["style_name"] = plain_label(task["style_name"], "style_name")
    if "pdf_fonts" in task:
        plan["pdf_fonts"] = task["pdf_fonts"]
    return Compilation(plan, task_raw, raw)


def compile_task(path):
    return compile_snapshot(path).plan
