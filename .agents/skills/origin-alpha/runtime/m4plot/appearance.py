"""Apply plain command options to a new CSV or a previously checked appearance."""

from .common import InputError
from .personal_styles import capture_profile, load_profile, style_for_figures
from .styles import APPLICABLE_FIELDS, RAW_FIELDS, resolve_style, segment_attributes


def _value(key, raw):
    if key in RAW_FIELDS:
        try:
            return float(raw)
        except ValueError as exc:
            raise InputError("STYLE_VALUE", key, "请输入正数。") from exc
    return raw


def _lookup(curves, selector, sample_names, *, rename=False):
    """Resolve display aliases to the same physical sample, including across pages."""
    matches = []
    for curve in curves:
        names = (curve["sample"], curve["label"], curve["id"], sample_names.get(curve["sample"]))
        if selector in names or (rename and selector == curve.get("segment")):
            matches.append(curve)
    if not matches or len({c["sample"] for c in matches}) != 1:
        raise InputError("SERIES_SELECTION", selector, "请指定能唯一对应一个样品的来源名、图例文字或曲线 ID。")
    if rename and len({c.get("segment") for c in matches}) != 1:
        raise InputError("SERIES_SELECTION", selector, "该样品有多个阶段，请指定要改名的阶段或完整图例文字。")
    return matches


def _segment_styles(style, figures, edits, global_edits):
    """Use source order for display defaults only. Reused and explicit choices win."""
    applicable = {}
    stages_by_sample = {}
    for figure in figures:
        for curve in figure["curves"]:
            if "segment" in curve:
                name = curve["segment"]
                applicable.setdefault(name, set()).update(APPLICABLE_FIELDS[curve["kind"]])
                stages_by_sample.setdefault(curve["sample"], {}).setdefault(name, None)
    defaults = {}
    if stages_by_sample:
        samples = {c["sample"] for f in figures for c in f["curves"]}
        bases = resolve_style(style, samples, figures)["samples"]
        for sample, names in stages_by_sample.items():
            base = bases[sample]
            other_lines = [s for s in ("dash", "dot", "solid") if s != base["line"]]
            other_fill = "open" if base["fill"] == "solid" else "solid"
            other_symbol = "square" if base["symbol"] == "circle" else "circle"
            # Keep the first branch in the sample style even if its marker
            # was already open or its line already dashed in a saved preset.
            alternatives = ({}, {"line": other_lines[0], "fill": other_fill},
                            {"line": other_lines[1], "symbol": other_symbol})
            for name, props in zip(names, alternatives):
                if props:
                    defaults.setdefault(name, props)
    inherited = style.get("segments", {})
    rules = {}
    for name, attrs in applicable.items():
        props = {k: v for k, v in defaults.get(name, {}).items() if k in attrs}
        props.update(inherited.get(name, {}))
        for key, value in global_edits or ():
            if key in props:
                props[key] = value
        if props:
            rules[name] = props
    for name, key, value in edits or ():
        if name not in applicable:
            raise InputError("SEGMENT_UNKNOWN", name, "请指定分段列中出现的阶段名称。")
        override = segment_attributes({key: value}, name)
        if key not in applicable[name]:
            raise InputError("STYLE_NOT_APPLICABLE", key, "该阶段的图型用不到此属性。")
        rules.setdefault(name, {}).update(override)
    if rules:
        style["segments"] = rules


def apply_appearance(task, args, *, previous=None, snapshot=None, library=None):
    """Apply global adjustments before series adjustments. Keep unedited draft properties."""
    figures = task["figures"]
    curves = [curve for figure in figures for curve in figure["curves"]]
    sample_names = task.get("grouping", {}).get("samples", {})
    for curve in curves:
        if previous is not None and args.kind:
            curve["kind"] = args.kind
    if args.title is not None:
        if len(figures) != 1:
            raise ValueError("请为每张图分别指定标题。")
        figures[0]["title"] = args.title

    current = task["style"]
    keep = previous is not None and args.preset is None
    name = args.preset or task.get("style_name", current["preset"])
    if keep:
        profile = snapshot if snapshot is not None else capture_profile(previous)
    else:
        profile = load_profile(name, library=library)
    defaults = dict(current.get("defaults", {})) if previous is None else {}
    samples = {}
    for label, settings in (current.get("samples", {}) if previous is None else {}).items():
        sample = _lookup(curves, label, sample_names)[0]["sample"]
        samples.setdefault(sample, {}).update(settings)

    for key, raw in args.adjust or ():
        defaults[key] = _value(key, raw)
        for attrs in samples.values():
            attrs.pop(key, None)
    for selector, key, raw in args.series or ():
        sample = _lookup(curves, selector, sample_names)[0]["sample"]
        samples.setdefault(sample, {})[key] = _value(key, raw)
    task["style"] = style_for_figures(name, figures, defaults=defaults, samples=samples, snapshot=profile)
    _segment_styles(task["style"], figures, getattr(args, "segment", None), args.adjust)
    task["style_name"] = name
    for figure in figures:
        if args.legend is not None:
            figure["legend_position"] = args.legend
        elif not keep:
            figure["legend_position"] = profile["legend_position"]
    # Resolve all renames against the original names, including swaps.
    labels = [(curve, value) for key, value in args.label or ()
              for curve in _lookup(curves, key, sample_names, rename=True)]
    if len({c["id"] for c, value in labels}) != len(labels):
        raise InputError("SERIES_SELECTION", "图例", "同一曲线收到多个图例名称，请指定一个。")
    for curve, label in labels:
        curve["label"] = label
    return profile, defaults
