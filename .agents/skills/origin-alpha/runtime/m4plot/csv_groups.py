"""Contiguous source groups represented by ordinary native curve row intervals."""

from .common import InputError, fields, text_value


def group_ranges(raw, column, names):
    from .planner import records
    rows = records(raw)
    headers = next(rows)
    if column not in headers:
        raise InputError("COLUMN_MISSING", "group_by", f"找不到分组列 {column!r}。")
    index = headers.index(column)
    selected = set(names)
    ranges = {}
    for number, row in enumerate(rows, 1):
        name = text_value(row[index], f"csv.data[{number}][{column!r}]")
        if selected and name not in selected:
            continue
        if name not in ranges:
            if len(ranges) >= 3:
                raise InputError("COUNT", "group_by", "检测到三个以上的组，请指定本图比较的最多三个样品。")
            ranges[name] = [number, number]
        else:
            if ranges[name][1] != number - 1:
                raise InputError("GROUP_INTERLEAVED", column,
                                 f"样品 {name!r} 在数据行 {number} 再次出现。当前入口要求同组行连续，请提供独立数值列或分组宽表。")
            ranges[name][1] = number
    missing = [name for name in names if name not in ranges]
    if missing:
        raise InputError("XY_SELECTION", "sample_names", f"分组列 {column!r} 中找不到样品 {missing!r}。")
    return ranges


def branch_ranges(raw, column, branch_column, names):
    """Read contiguous labelled intervals without deriving phases from X or duplicating turnarounds."""
    from .planner import records
    rows = records(raw)
    headers = next(rows)
    if branch_column == column or branch_column not in headers:
        raise InputError("BRANCH_COLUMN", "branch_column", "请指定与样品列不同的原始阶段列。")
    group_index, branch_index = headers.index(column), headers.index(branch_column)
    ranges = {name: {} for name in names}
    for number, row in enumerate(rows, 1):
        name = row[group_index]
        if name not in ranges:
            continue
        segment = text_value(row[branch_index], f"csv.data[{number}][{branch_column!r}]")
        branches = ranges[name]
        if segment not in branches:
            if len(branches) == 3:
                raise InputError("COUNT", "branch_column", "每张图最多三条分段曲线，请核对所选样品和阶段。")
            branches[segment] = [number, number]
        elif branches[segment][1] != number - 1:
            raise InputError("BRANCH_INTERLEAVED", branch_column,
                             f"样品 {name!r} 的 {segment!r} 在第 {number} 行再次出现。多次循环请使用可区分各次过程的原始阶段标签。")
        else:
            branches[segment][1] = number
    return ranges


def validate_grouping(raw, grouping, figures, columns):
    """Recheck any saved grouped task against raw cells. Labels can be customized."""
    fields(grouping, "grouping", ("column", "samples"), ("branch_column",))
    column = text_value(grouping["column"], "grouping.column")
    if column in columns:
        raise InputError("GROUP_COLUMN", "grouping.column", "分组列与绘图数值列须分开。")
    samples = grouping["samples"]
    if not isinstance(samples, dict) or not 1 <= len(samples) <= 3:
        raise InputError("GROUP_SAMPLES", "grouping.samples", "请为每条曲线保留来源组名。")
    names = [text_value(name, "grouping.samples") for name in samples.values()]
    if len(names) != len(set(names)):
        raise InputError("GROUP_SAMPLES", "grouping.samples", "不同样品须对应不同原始组名。")
    curves = [curve for fig in figures for curve in fig["curves"]]
    if set(samples) != {curve["sample"] for curve in curves}:
        raise InputError("GROUP_SAMPLES", "grouping.samples", "曲线样品与来源组名不相符。")
    bounds = group_ranges(raw, column, names)
    if "branch_column" in grouping:
        branch = text_value(grouping["branch_column"], "grouping.branch_column")
        if branch in columns:
            raise InputError("BRANCH_COLUMN", branch, "阶段标签与绘图数值须来自不同的列。")
        split = branch_ranges(raw, column, branch, names)
    else:
        split = None
    for figure in figures:
        represented = {}
        for curve in figure["curves"]:
            name = samples[curve["sample"]]
            if split is None:
                if "segment" in curve:
                    raise InputError("BRANCH_COLUMN", column, "曲线给出了阶段，请绑定阶段来源列。")
                expected = bounds[name]
            else:
                segment = curve.get("segment")
                if segment not in split[name]:
                    raise InputError("BRANCH_LABEL", column, f"样品 {name!r} 的阶段 {segment!r} 无法在来源列中核实。")
                seen = represented.setdefault(name, [])
                if segment in seen:
                    raise InputError("BRANCH_DUPLICATE", column, f"同一图重复绘制了样品 {name!r} 的阶段 {segment!r}。")
                seen.append(segment)
                expected = split[name][segment]
            if curve["rows"] != expected:
                raise InputError("GROUP_RANGE", "grouping.samples", f"{name!r} 的曲线行范围与 CSV 分组不符。")
        if split is not None and represented.keys() != split.keys():
            raise InputError("BRANCH_COVERAGE", branch, "每张分段图均须包含本次选定的全部样品。")
        for name, segments in represented.items():
            if segments != list(split[name]):
                raise InputError("BRANCH_COVERAGE", branch, f"此图须依采集顺序覆盖样品 {name!r} 的全部原始阶段。")
    return grouping

