"""Independent CSV and plan verification from the frozen offline science check."""

import csv
from decimal import Decimal
import io
import math

from .common import digest, sha256
from .paths import require
from .science_headers import canonical_unit, classify, error_unit_scale, explicitly_relative


def check_science(task, compilation, preset):
    """Second implementation using stdlib CSV, the source decimal tokens and task mappings."""
    plan = compilation.plan
    data = plan["data"]
    require(plan.get("style_name") == task.get("style_name"), "显示的风格名与任务不符。")
    require(("pdf_fonts" in plan) == ("pdf_fonts" in task) and plan.get("pdf_fonts") == task.get("pdf_fonts")
            and ("pdf_fonts" not in task or
                 (task["schema"] == "m4-mvp1.task/3" and task["pdf_fonts"] == "request-embedded")),
            "计划中的 PDF 字体请求与任务不符。")
    require(plan["schema"] == "m4-mvp1.plan/1" and plan["status"] == "OFFLINE_PLAN"
            and plan["native_authorized"] is False and plan["native_observed"] is False
            and plan["task_sha256"] == sha256(compilation.task_bytes)
            and data["source_name"] == task["csv"] and data["kind"] == task["data_kind"]
            and data["source_sha256"] == sha256(compilation.csv_bytes), "任务与计划来源不符。")
    rows = csv.reader(io.StringIO(compilation.csv_bytes.decode("utf-8-sig"), newline=""), strict=True)
    headers = next(rows)
    grouping = task.get("grouping")
    require(data.get("grouping") == grouping, "计划与任务的来源分组不符。")
    branch_index = None
    if grouping:
        group_index = headers.index(grouping["column"])
        raw_groups = {name: [] for name in grouping["samples"].values()}
        if "branch_column" in grouping:
            branch_index = headers.index(grouping["branch_column"])
            raw_branches = {name: {} for name in raw_groups}
    selected = [(i, h) for i, h in enumerate(headers) if h in task["columns"]]
    columns = data["columns"]
    error_definitions, axes_used = {}, set()
    for fig in task["figures"]:
        for curve in fig["curves"]:
            axes_used.update([curve["x"], curve["y"]])
            if "y_error" not in curve:
                continue
            binding = curve["y_error"]
            require(task["schema"] == "m4-mvp1.task/3" and set(binding) == {"column", "definition"}
                    and isinstance(binding["definition"], str) and binding["definition"].strip(), "缺少误差列定义。")
            header, y_header = binding["column"], curve["y"]
            require(header in headers and header in task["columns"], "误差列并非来自原 CSV 数值列。")
            require(error_definitions.setdefault(header, binding["definition"]) == binding["definition"],
                    "同一 CSV 误差列具有冲突的含义。")
            units = [canonical_unit(task["columns"][h]["unit"]) for h in (header, y_header)]
            require(not explicitly_relative(header, task["columns"][header]["quantity"], binding["definition"]),
                    "相对误差不可用作绝对半宽。")
            require(error_unit_scale(units[0]) == units[1] and all(classify(h).unit in (None, unit) for h, unit in
                    zip((header, y_header), units, strict=True)), "误差单位与 Y 列或原始表头不符。")
    require(not (axes_used & error_definitions.keys()), "误差列与坐标列绑定重叠。")
    require([col["header"] for col in columns] == [h for _, h in selected]
            and plan["excluded_csv_headers"] == [h for h in headers if h not in task["columns"]],
            "选入、排除列或列序与 CSV 不符。")
    for col in columns:
        metadata = task["columns"][col["header"]]
        require(col["quantity"] == metadata["quantity"] and col["unit"] == metadata["unit"],
                "物理量或单位与任务不符。")
        require(len(col["tokens"]) == len(col["values"]) == data["row_count"], "计划数列长度不符。")
    count = 0
    for count, row in enumerate(rows, 1):
        require(len(row) == len(headers) and count <= data["row_count"], "CSV 记录数或行宽有误。")
        if grouping and row[group_index] in raw_groups:
            name = row[group_index]
            raw_groups[name].append(count)
            if branch_index is not None:
                raw_branches[name].setdefault(row[branch_index], []).append(count)
        for (position, header), column in zip(selected, columns, strict=True):
            token = row[position]
            value = column["values"][count - 1]
            if header in error_definitions:
                require(math.isfinite(value) and value >= 0, f"原始误差列 {header!r} 的数据行 {count} 无效。")
            require(column["tokens"][count - 1] == token and type(value) is float
                    and Decimal(str(value)) == Decimal(token.strip())
                    and value.hex() == float(token.strip()).hex(),
                    f"原 CSV 与计划不符：数据行 {count}，列 {header}。")
    require(count == data["row_count"], "CSV 与计划行数不符。")

    positions = {name: index for index, (_, name) in enumerate(selected, 1)}
    pages = {}
    samples = set()
    for gi, (source, figure) in enumerate(zip(task["figures"], data["figures"], strict=True), 1):
        first = source["curves"][0]
        axes = {axis: task["columns"][first[axis]] for axis in ("x", "y")}
        require(figure["title"] == source["title"] and figure["id"] == source["id"] and figure["axes"] == axes,
                "图名、顺序或坐标轴与任务不符。")
        require(figure.get("legend_position") == source.get("legend_position"), "图例位置与任务不符。")
        mapping = {}
        branch_coverage = {}
        pi = 1
        for item, curve in zip(source["curves"], figure["curves"], strict=True):
            bounds = item.get("rows", [1, count])
            if grouping:
                source_name = grouping["samples"][item["sample"]]
                source_rows = raw_groups[source_name]
                if branch_index is not None:
                    source_rows = raw_branches[source_name].get(item.get("segment"))
                    branch_coverage.setdefault(source_name, []).extend(range(bounds[0], bounds[1] + 1))
                require(source_rows == list(range(bounds[0], bounds[1] + 1)),
                        f"样品 {source_name!r} 的原始分组行与曲线行范围不符。")
            require(curve == {**item, "rows": bounds}, "组别、图例、类型、XY 或行区间与任务不符。")
            mapping[item["id"]] = dict(plot=pi, sample=item["sample"], rows=bounds,
                                       x_column=positions[item["x"]], y_column=positions[item["y"]])
            if "y_error" in item:
                err_col = positions[item["y_error"]["column"]]
                y_values = columns[positions[item["y"]] - 1]["values"]
                half_widths = columns[err_col - 1]["values"]
                for row in range(bounds[0] - 1, bounds[1]):
                    require(all(math.isfinite(limit) for limit in (y_values[row] - half_widths[row],
                                                                    y_values[row] + half_widths[row])),
                            "误差棒端点超出数值范围。")
                mapping[item["id"]].update(y_error_column=err_col, error_plot=pi + 1)
                pi += 1
            pi += 1
            samples.add(item["sample"])
        if branch_index is not None:
            require(branch_coverage.keys() == raw_groups.keys(), "分图未覆盖本次选定的全部样品。")
        for name, covered in branch_coverage.items():
            require(covered == raw_groups[name], f"样品 {name!r} 的阶段曲线未按原始行序完整覆盖。")
        pages[source["id"]] = dict(page=f"M4Fig{gi}", layer=1, curves=mapping)
    require(plan["object_map"] == dict(workbook="M4Data", worksheet="Raw", figures=pages),
            "计划中的工作表与曲线绑定不符。")
    requested = task["style"]
    expected = {}
    for sample, slot in zip(sorted(samples), preset["slots"]):
        style = {**preset["defaults"], **slot, **requested.get("defaults", {}),
                 **requested.get("samples", {}).get(sample, {})}
        style["color"] = style["color"].upper()
        for size in ("line_width", "symbol_size"):
            style[size] = float(style[size])
        expected[sample] = style
    expected_styles = dict(preset=requested["preset"], preset_version=preset["version"],
                           preset_content_sha256=digest(preset), samples=expected)
    if requested.get("segments"):
        expected_styles["segments"] = requested["segments"]
    require(plan["styles"] == expected_styles,
            "图形样式与实际预设、任务覆盖值不符。")
    require(plan["data_sha256"] == digest(data) and plan["style_sha256"] == digest(plan["styles"]),
            "计划数据或样式摘要不符。")
