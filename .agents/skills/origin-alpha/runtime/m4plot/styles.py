"""Resolve sample styles for offline plans without assigning Origin enum values."""

import re
import sys
from pathlib import Path

from .common import InputError, digest, load_bytes, parse_json, sha256


PRESET_DIRECTORY = Path(__file__).resolve().parent.parent / "presets"
PRESET_IDS = {"clean", "mono"}
PRESET_FIELDS = {"schema", "id", "version", "defaults", "slots"}
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
ENUMS = {
    "symbol": {"circle", "square"},
    "fill": {"solid", "open"},
    "line": {"solid", "dash", "dot"},
}
RAW_FIELDS = {"line_width", "symbol_size"}
STYLE_FIELDS = {"color"} | set(ENUMS) | RAW_FIELDS
SEGMENT_FIELDS = {"line", "symbol", "fill"}
VISUAL_FIELDS = {
    "scatter": ("color", "symbol", "fill"),
    "line": ("color", "line"),
    "linesymbol": ("color", "line", "symbol", "fill"),
}
APPLICABLE_FIELDS = {
    "scatter": set(VISUAL_FIELDS["scatter"]) | {"symbol_size"},
    "line": set(VISUAL_FIELDS["line"]) | {"line_width"},
    "linesymbol": STYLE_FIELDS,
}


def _object(value, field):
    if not isinstance(value, dict):
        raise InputError("STYLE_OBJECT", field, "Expected an object.")
    return value


def _check_fields(values, allowed, field):
    for name in values:
        if name not in allowed:
            raise InputError("STYLE_FIELD", f"{field}.{name}", "Unknown style field.")


def _attributes(value, field):
    values = _object(value, field)
    _check_fields(values, STYLE_FIELDS, field)
    normalized = {}
    for name, item in values.items():
        path = f"{field}.{name}"
        if name == "color":
            if not isinstance(item, str) or HEX_COLOR.fullmatch(item) is None:
                raise InputError("STYLE_COLOR", path, "Expected a six-digit color such as #0072B2.")
            normalized[name] = item.upper()
        elif name in RAW_FIELDS:
            if type(item) not in (int, float) or not 0 < item <= sys.float_info.max:
                raise InputError("STYLE_RAW_VALUE", path, "Expected a finite positive raw number.")
            normalized[name] = float(item)
        else:
            if not isinstance(item, str) or item not in ENUMS[name]:
                choices = ", ".join(sorted(ENUMS[name]))
                raise InputError("STYLE_ENUM", path, f"Supported values are {choices}.")
            normalized[name] = item
    return normalized


def segment_attributes(value, field):
    attrs = _attributes(value, field)
    _check_fields(attrs, SEGMENT_FIELDS, field)
    if not attrs:
        raise InputError("SEGMENT_STYLE", field, "请给出阶段的线型、点形或填充。")
    return attrs


def curve_style(styles, curve):
    sample = styles["samples"][curve["sample"]]
    overrides = styles.get("segments", {}).get(curve.get("segment"))
    return {**sample, **overrides} if overrides else sample


def _load_preset(preset_id):
    pinned = {
        "clean": "6081bce14952084a19b598d8e88907ea76d3234eedd5d5d96332b72b9d386718",
        "mono": "f48e44a24c582589a7ae6c4336ebfc57db6e319327f241d85e40af5442da1260",
    }
    if preset_id not in pinned:
        raise InputError("STYLE_PRESET_CONTRACT", "preset", "未知的内置样式基底。")
    raw = load_bytes(PRESET_DIRECTORY / f"{preset_id}.json", 256 * 1024)
    if sha256(raw) != pinned[preset_id]:
        raise InputError("STYLE_PRESET_CHANGED", preset_id, "随包预设字节已变更。请重新提取公开候选。")
    preset = parse_json(raw, preset_id)
    field = f"presets.{preset_id}"
    if (not isinstance(preset, dict) or set(preset) != PRESET_FIELDS
            or preset["schema"] != "m4-mvp1.style-preset/1" or preset["id"] != preset_id
            or not isinstance(preset["version"], str) or not preset["version"]
            or not isinstance(preset["slots"], list) or len(preset["slots"]) != 3):
        raise InputError("STYLE_PRESET_CONTRACT", field, "Invalid bundled preset.")
    defaults = _attributes(preset["defaults"], f"{field}.defaults")
    samples = []
    for index, slot in enumerate(preset["slots"]):
        slot_field = f"{field}.slots[{index}]"
        values = {**defaults, **_attributes(slot, slot_field)}
        if set(values) != STYLE_FIELDS:
            raise InputError("STYLE_PRESET_CONTRACT", slot_field, "Preset slot needs all style fields.")
        samples.append(values)
    return preset, samples


def _check_applicability(overrides, applicable, field):
    for name in overrides:
        if name not in applicable:
            raise InputError(
                "STYLE_NOT_APPLICABLE", f"{field}.{name}",
                "No associated curve uses this attribute. Remove it or change the curve kind.",
            )


def _check_visual_conflicts(figures, styles):
    for index, figure in enumerate(figures):
        encodings = {}
        for curve in figure["curves"]:
            sample = curve["sample"]
            kind = curve["kind"]
            values = curve_style(styles, curve)
            encoding = (kind, *(values[name] for name in VISUAL_FIELDS[kind]))
            previous = encodings.setdefault(encoding, sample)
            if previous != sample:
                figure_id = figure.get("id", index + 1)
                raise InputError(
                    "STYLE_VISUAL_CONFLICT", f"style.samples.{sample}",
                    f"Samples {previous!r} and {sample!r} use the same visual encoding "
                    f"in figure {figure_id!r}. Change a color, applicable symbol, or fill.",
                )


def resolve_style(style, sample_ids, figures):
    """Apply the preset, task defaults and sample overrides in that order."""
    style = _object(style, "style")
    _check_fields(style, {"preset", "defaults", "samples", "segments"}, "style")
    preset_id = style.get("preset")
    if not isinstance(preset_id, str) or preset_id not in PRESET_IDS:
        raise InputError("STYLE_PRESET", "style.preset", "Choose clean or mono.")

    samples_sorted = sorted(sample_ids)
    if len(samples_sorted) > 3 or len(set(samples_sorted)) != len(samples_sorted):
        raise InputError("STYLE_SAMPLES", "style.samples", "Expected at most three distinct sample IDs.")

    defaults = _attributes(style.get("defaults", {}), "style.defaults")
    requested_samples = _object(style.get("samples", {}), "style.samples")
    for sample in requested_samples:
        if sample not in samples_sorted:
            raise InputError("STYLE_SAMPLE", f"style.samples.{sample}", "Unknown sample ID.")

    applicable_by_sample = {sample: set() for sample in samples_sorted}
    for figure in figures:
        for curve in figure["curves"]:
            applicable_by_sample[curve["sample"]].update(APPLICABLE_FIELDS[curve["kind"]])
    _check_applicability(defaults, set().union(*applicable_by_sample.values()), "style.defaults")

    preset, slots = _load_preset(preset_id)
    samples = {}
    for sample, slot in zip(samples_sorted, slots):
        field = f"style.samples.{sample}"
        overrides = _attributes(requested_samples.get(sample, {}), field)
        _check_applicability(overrides, applicable_by_sample[sample], field)
        effective = {**slot, **defaults, **overrides}
        if effective["color"] == "#FFFFFF":
            color_field = "style.preset"
            if "color" in overrides:
                color_field = f"{field}.color"
            elif "color" in defaults:
                color_field = "style.defaults.color"
            raise InputError(
                "STYLE_BACKGROUND_CONTRAST", color_field,
                f"样品 {sample} 的曲线或数据点使用纯白色 #FFFFFF，会与固定的白色背景融在一起。请选择其他颜色。",
            )
        samples[sample] = effective
    resolved = {
        "preset": preset_id,
        "preset_version": preset["version"],
        "preset_content_sha256": digest(preset),
        "samples": samples,
    }
    if "segments" in style:
        by_segment = {}
        for figure in figures:
            for curve in figure["curves"]:
                if "segment" in curve:
                    by_segment.setdefault(curve["segment"], set()).update(APPLICABLE_FIELDS[curve["kind"]])
        segments = {}
        for name, props in _object(style["segments"], "style.segments").items():
            if name not in by_segment:
                raise InputError("SEGMENT_UNKNOWN", str(name), "该阶段名称未绑定本图中的原始数据。")
            field = "style.segments." + name
            attrs = segment_attributes(props, field)
            _check_applicability(attrs, by_segment[name], field)
            segments[name] = attrs
        if segments:
            resolved["segments"] = segments
    _check_visual_conflicts(figures, resolved)
    return resolved
