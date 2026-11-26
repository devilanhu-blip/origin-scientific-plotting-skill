"""Explicit semantics for same-unit absolute symmetric Y half-widths."""

import re


STATISTICS = {
    "SD": re.compile(r"(?<![a-z0-9])(?:sd|std|stdev|stddev|standard[ _-]+deviation)(?![a-z0-9])|标准差|标准偏差", re.I),
    "SEM": re.compile(r"(?<![a-z0-9])(?:sem|se|stderr|standard[ _-]+error)(?![a-z0-9])|标准误", re.I),
    "CI": re.compile(r"(?<![a-z0-9])(?:ci|confidence[ _-]+interval)(?![a-z0-9])|置信区间", re.I),
}
HALF_WIDTH_BASIS = re.compile(r"半[宽寬]|half[ _-]*width", re.I)
UNDEFINED_ERROR = re.compile(
    r"未知|不详|不知道|不清楚|不明确|待确认|待核实|待定|未(?:提供|说明|定义|确认)"
    r"|\b(?:unknown|undefined|unspecified|not known|not specified|tbd|n/a)\b", re.I
)
BARE_ERROR = re.compile(
    r"(?:\d+(?:\.\d+)?\s*[%％]|百分比(?:误差)?|(?:相对|测量|实验|仪器|设备|绝对|对称)误差|上界|下界|"
    r"(?:对称|绝对|误差)*半宽|upper bound|lower bound|percentage|percent|"
    r"(?:relative|measurement|instrument|absolute|symmetric) error|(?:absolute )?half[ _-]*width)",
    re.IGNORECASE,
)
BOUND_COLUMN = re.compile(
    r"(?:上界|下界|(?:区间|置信)[上下]限)|"
    r"(?<![a-z0-9])(?:upper|lower)[ _-]+(?:ci|bound|limit)(?![a-z0-9])",
    re.IGNORECASE,
)


def validate_error(column, definition):
    from .common import InputError
    from .science_headers import explicitly_relative

    if explicitly_relative(column, definition):
        raise InputError("ERROR_DEFINITION", column, "此列或定义表明是相对量，请提供已换算的绝对半宽列。")
    if (UNDEFINED_ERROR.search(definition) or BARE_ERROR.fullmatch(definition.strip())
            or BOUND_COLUMN.search(column)):
        raise InputError("ERROR_DEFINITION", column, "请给出材料明确的绝对半宽定义或转换依据。")
    stated = {label for label, pattern in STATISTICS.items() if pattern.search(definition)}
    header = {label for label, pattern in STATISTICS.items() if pattern.search(column)}
    if not header.issubset(stated) or (stated and not HALF_WIDTH_BASIS.search(definition)):
        raise InputError("ERROR_DEFINITION", column, "请按材料说明该统计量怎样成为与 Y 同单位的对称绝对半宽。")
