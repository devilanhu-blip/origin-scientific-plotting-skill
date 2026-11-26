"""Interpret explicit quantities and unit spellings in wide scientific CSV headers."""

from dataclasses import dataclass
import re


# Units in one row of this table can have different scales. Only spelling aliases
# below are normalized; a plot must still use the *same* unit on a shared axis.
SCIENCE = {
    "时间": ("x", ("time",), {"s", "ms", "µs", "ns", "min", "h", "d"}),
    "波长": ("x", ("wavelength", "λ"), {"nm", "µm", "mm", "cm", "m", "Å"}),
    "光子能量": ("x", ("photon energy",), {"eV", "meV", "keV", "J"}),
    "温度": ("temperature", ("temperature", "temp"), {"K", "°C", "°F"}),
    "塞贝克系数": ("y", ("seebeck", "seebeck coefficient", "热电势系数"), {"V/K", "mV/K", "µV/K"}),
    "电导率": ("y", ("electrical conductivity", "电导率", "电导系数", "σ"), {"S/m", "S/cm", "mS/cm", "kS/m"}),
    "电阻率": ("y", ("electrical resistivity", "resistivity", "ρ"), {"Ω·m", "Ω·cm", "mΩ·cm", "µΩ·cm"}),
    "热导率": ("y", ("thermal conductivity", "导热系数", "热导系数", "κ"),
            {"W/(m·K)", "mW/(m·K)", "W/(cm·K)"}),
    "功率因子": ("y", ("power factor", "PF"), {"W/(m·K²)", "mW/(m·K²)", "µW/(cm·K²)", "µW/(m·K²)"}),
    "热电优值": ("y", ("ZT", "thermoelectric figure of merit", "热电优值ZT", "无量纲热电优值"), {"1"}),
    "吸光度": ("y", ("absorbance",), {"1", "AU"}),
    "透射率": ("y", ("transmittance", "透过率"), {"%", "1"}),
    "反射率": ("y", ("reflectance",), {"%", "1"}),
    "吸收率": ("y", ("absorptance",), {"%", "1"}),
    "光强": ("y", ("intensity", "光谱强度"), {"a.u.", "count", "count/s", "W/m²"}),
    "发光强度": ("y", ("PL intensity", "emission intensity", "荧光强度"), {"a.u.", "count", "count/s"}),
    "探测器计数": ("y", ("counts", "detector counts", "emission"), {"count"}),
    "电压": ("y", ("voltage",), {"V", "mV", "µV", "nV"}),
}
SEPARATORS = r"[_\s-]+"
SYMBOLS = {"T": "温度", "t": "时间", "S": "塞贝克系数"}


def _key(text):
    return re.sub(SEPARATORS, " ", text.strip()).casefold()


QUANTITIES = {_key(alias): name for name, (_, aliases, _) in SCIENCE.items() for alias in (name, *aliases)}
COMMON_UNITS = {name: spec[2] for name, spec in SCIENCE.items()}
ALIASES = {
    "degC": "°C", "℃": "°C", "degF": "°F", "℉": "°F", "counts": "count", "counts/s": "count/s",
    "arb. units": "a.u.", "a. u.": "a.u.", "dimensionless": "1", "无量纲": "1",
    "ohm m": "Ω·m", "ohm cm": "Ω·cm", "Ω m": "Ω·m", "Ω cm": "Ω·cm",
}
for prefix in ("V", "mV", "µV"):
    for exp in ("K^-1", "K-1", "K−1", "K⁻¹"):
        ALIASES[prefix + " " + exp] = prefix + "/K"
        ALIASES[prefix + "·" + exp] = prefix + "/K"
for prefix, length in (("S", "m"), ("S", "cm"), ("mS", "cm"), ("kS", "m")):
    for exp in ("^-1", "-1", "−1", "⁻¹"):
        ALIASES[f"{prefix} {length}{exp}"] = f"{prefix}/{length}"
        ALIASES[f"{prefix}·{length}{exp}"] = f"{prefix}/{length}"
for prefix, length, power in (
    ("W", "m", 1), ("mW", "m", 1), ("W", "cm", 1), ("W", "m", 2),
    ("mW", "m", 2), ("µW", "cm", 2), ("µW", "m", 2),
):
    k = "K" if power == 1 else "K²"
    standard = f"{prefix}/({length}·{k})"
    for spelling in (k, "K" if power == 1 else "K^2", "K" if power == 1 else "K2"):
        ALIASES[f"{prefix}/({length} {spelling})"] = standard
        ALIASES[f"{prefix}/({length}·{spelling})"] = standard
        ALIASES[f"{prefix}/{length}/{spelling}"] = standard
    for first, second in (("-1", f"-{power}"), ("−1", f"−{power}"), ("^-1", f"^-{power}"),
                          ("⁻¹", "⁻¹" if power == 1 else "⁻²")):
        for join in (" ", "·"):
            ALIASES[f"{prefix}{join}{length}{first}{join}K{second}"] = standard

OTHER_UNITS = {"kg", "g", "mg", "mol", "N", "Pa", "J", "W", "A", "Hz"}
KNOWN_UNITS = set().union(*COMMON_UNITS.values(), OTHER_UNITS, ALIASES)
# ASCII 'u' is accepted only for known micro-prefixed units.
for micro in tuple(KNOWN_UNITS):
    if "µ" in micro:
        for variant in ("u", "μ"):
            ALIASES[micro.replace("µ", variant)] = ALIASES.get(micro, micro)
KNOWN_UNITS.update(ALIASES)


def canonical_unit(unit):
    return ALIASES.get(unit, unit)


def error_unit_scale(unit):
    """A half-width in percentage points uses the numeric scale of a percentage-valued Y."""
    if unit.casefold() in {"百分点", "percentage point", "percentage points", "pp", "p.p."}:
        return "%"
    return canonical_unit(unit)


RELATIVE_ERROR = re.compile(
    r"相对(?:标准偏差|标准差|标准误|误差|不确定度|扩展不确定度|容差)|变异系数|百分比误差|百分误差"
    r"|(?<![a-z0-9])(?:rsd|rse|coefficient[ _-]+of[ _-]+variation|(?:relative|percentage|percent)"
    r"[ _-]+(?:standard[ _-]+)?(?:deviation|error|uncertainty|tolerance))(?![a-z0-9])"
    r"|(?<![a-z0-9])cv(?=$|\s*[\[(])|%\s*(?:of\s+(?:reading|value)|读数)", re.I)


def explicitly_relative(*descriptions):
    return any(RELATIVE_ERROR.search(description) for description in descriptions)


def canonical_quantity(name):
    return SYMBOLS.get(name, QUANTITIES.get(_key(name), name))


AUXILIARY = {
    "note", "notes", "remark", "remarks", "observation", "备注", "采样备注", "说明", "序号",
    "row", "row id", "row number", "index", "timestamp", "时间戳",
}
GROUPING = {"sample", "sample id", "sample name", "material", "group", "group id", "specimen",
            "样品", "样品名", "样品名称", "样品编号", "样品id", "材料", "组别"}
STAGE_LABELS = {"阶段", "采样阶段", "测量阶段", "升降温阶段", "升降温方向", "温程", "stage",
                "measurement stage", "cycle stage", "sweep direction", "ramp direction"}
ERROR_MARKER = re.compile(r"(?:^|[_\s-])(?:sd|sem|rsd|rse|stderr|stdev|stddev|std|error|uncertainty|standard deviation|standard error|coefficient of variation)(?=$|[_\s-])"
                          r"|标准差|标准误|标准偏差|变异系数|不确定度|误差", re.I)


@dataclass(frozen=True)
class Heading:
    quantity: str
    unit: str | None
    role: str
    sample: str


def _split_unit(header):
    # An underscore unit can itself contain slashes or parentheses.
    suffix = header.rpartition("_")
    if suffix[1] and suffix[2] in KNOWN_UNITS and suffix[2] != "A":
        return suffix[0].strip(), canonical_unit(suffix[2])
    # For a bracketed unit, keep the whole content, e.g. W/(m·K).
    for opening, closing in (("[", "]"), ("（", "）"), ("(", ")")):
        if header.endswith(closing) and opening in header:
            base, unit = header[:-1].split(opening, 1)
            if base.strip() and unit.strip() and (opening != "(" or not base.endswith("/")):
                return base.strip(), canonical_unit(unit.strip())
    base, sep, unit = header.partition("/")
    if sep and base.strip() and unit.strip():
        return base.strip(), canonical_unit(unit.strip())
    return header.strip(), None


def _recognize(base):
    def match(text):
        return SYMBOLS.get(text, QUANTITIES.get(_key(text)))

    if quantity := match(base):
        return quantity, ""
    # Match at either end and prefer the longest known quantity. The rest
    # stays exactly as written, including punctuation within a sample name.
    candidates = []
    for split in re.finditer(SEPARATORS, base):
        left, right = base[:split.start()], base[split.end():]
        if right and (quantity := match(left)):
            candidates.append((len(left), quantity, right))
        if left and (quantity := match(right)):
            candidates.append((len(right), quantity, left))
    if not candidates:
        return base, ""
    _, quantity, sample = max(candidates)
    return quantity, sample


def classify(header):
    base, unit = _split_unit(header)
    key = _key(base)
    if key in GROUPING:
        return Heading(base, unit, "group", "")
    if key in AUXILIARY or ERROR_MARKER.search(base) or (unit is None and key in STAGE_LABELS):
        return Heading(base, unit, "auxiliary", "")
    quantity, sample = _recognize(base)
    if quantity not in SCIENCE:
        return Heading(base, unit, "unknown", "")
    if quantity == "探测器计数" and "emission" in key and unit not in COMMON_UNITS[quantity]:
        return Heading(base, unit, "unknown", "")
    explicit_zt = re.search(r"(?:^|[_\s-])zt(?:$|[_\s-])|热电优值zt|无量纲热电优值", base, re.I)
    if unit is None and (quantity == "吸光度" or (quantity == "热电优值" and explicit_zt)):
        unit = "1"
    return Heading(quantity, unit, SCIENCE[quantity][0], sample)


def describe_headers(headers):
    """Hints from exact headings for an assistant to present alongside the raw CSV preview."""
    headings = {h: classify(h) for h in headers}
    for_temperature = temperature_role(headings)
    return [dict(header=h, quantity=info.quantity, unit=info.unit,
                 role=for_temperature if info.role == "temperature" else info.role, sample=info.sample)
            for h, info in headings.items()]


def temperature_role(headings):
    primary = {info.quantity for info in headings.values() if info.role == "x"}
    if not primary:
        return "x"
    if primary == {"时间"} and not any(info.role == "y" for info in headings.values()):
        return "y"
    return "x_or_y"

