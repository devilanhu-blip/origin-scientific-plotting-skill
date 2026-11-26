"""Readable offline plan with original column and row bindings."""

from .common import figure_title
from .legend_layout import POSITIONS
from .science_headers import canonical_unit
from .styles import curve_style


def preview(plan):
    data = plan["data"]
    units = {column["header"]: column["unit"] for column in data["columns"]}
    style = plan["styles"]
    lines = [
        f"离线绘图计划  {data['kind']}  |  {data['source_name']}  |  {data['row_count']} 个数据行",
        f"风格  {plan['style_name']}    背景  白色",
    ]
    if "grouping" in data:
        group = data["grouping"]
        members = "、".join(group["samples"].values())
        lines.append(f"按 CSV 的「{group['column']}」列分组，保留原始行序    {members}")
        if "branch_column" in group:
            lines.append(f"各样品按「{group['branch_column']}」列的原始阶段分别绘制，跨阶段断开。")
    for figure in data["figures"]:
        axes = figure["axes"]
        title = figure_title(data, figure)
        lines.extend(["", f"{figure['id']}  {title}",
                      "    " + "    ".join(f"{k.upper()}  {axes[k]['quantity']} / {axes[k]['unit']}" for k in ("x", "y"))])
        if "legend_position" in figure:
            lines.append("    图例  " + POSITIONS[figure["legend_position"]])
        for curve in figure["curves"]:
            lo, hi = curve["rows"]
            kind = curve["kind"]
            description = {"scatter": "散点图", "line": "折线图", "linesymbol": "点线图"}[kind]
            label = curve["label"]
            if "grouping" in data:
                original = data["grouping"]["samples"][curve["sample"]]
                if "segment" in curve:
                    label += f"（源样品 {original}，阶段 {curve['segment']}）"
                elif original != label:
                    label += f"（原始组：{original}）"
            lines.append(f"    {label}  {description}  "
                         f"X={curve['x']}   Y={curve['y']}   数据行 {lo}–{hi}（{hi-lo+1} 点）")
            if "y_error" in curve:
                error = curve["y_error"]
                error_unit = units[error["column"]]
                if canonical_unit(error_unit) == "%":
                    error_unit += "（绝对幅度按百分点计）"
                lines.append(f"        对称 Y 误差列「{error['column']}」，绝对半宽单位 {error_unit}，"
                             f"{error['definition']}，对应原数据行 {lo}–{hi}")
            values = curve_style(style, curve)
            attributes = [values["color"]]
            if kind in ("line", "linesymbol"):
                pattern = {"solid": "实线", "dash": "虚线", "dot": "点状线"}[values["line"]]
                attributes.append(f"{pattern}，线宽 {values['line_width']:g}")
            if kind in ("scatter", "linesymbol"):
                shape = {"circle": "圆", "square": "方块"}[values["symbol"]]
                fill = {"solid": "实心", "open": "空心"}[values["fill"]]
                attributes.append(f"{fill}{shape}，点大小 {values['symbol_size']:g}")
            lines.append("        " + "　".join(attributes))
    if plan["excluded_csv_headers"]:
        lines.append("未绑定为 X、Y 或误差数值的源列  " + "、".join(plan["excluded_csv_headers"]))
    lines.extend(["", f"源 CSV SHA-256  {data['source_sha256']}", f"系列样式 SHA-256  {plan['style_sha256']}"])
    return "\n".join(lines)
