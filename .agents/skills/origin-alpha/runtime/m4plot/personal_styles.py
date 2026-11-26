"""Project-local personal styles, compiled to ordinary self-contained M4 tasks."""

import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from .common import InputError, fields, read_json, sha256, text_value
from .legend_layout import check_position
from .paths import local_path
from .planner import identifier
from .styles import APPLICABLE_FIELDS, PRESET_IDS, STYLE_FIELDS, _attributes, _load_preset, resolve_style


PROFILE_SCHEMA = "m4plot.personal-style/1"
BUILTINS = ("clean", "mono", "汇报")
ALIASES = {"清晰": "clean", "单色": "mono", "论文": "clean", "黑白": "mono", "演示": "汇报"}
TALK_COLORS = ("#174C80", "#B54E12", "#49753A")


def _name(value):
    return unicodedata.normalize("NFC", text_value(value, "风格名"))


def _builtin(name):
    key = name.casefold()
    return key if key in BUILTINS else ALIASES.get(key)


def _path(folder, name):
    # The display name is stored in the file, so punctuation cannot affect the path.
    return Path(folder) / (sha256(name.casefold().encode("utf-8")) + ".json")


def _selector(value):
    """A bare name means personal. An explicit library may pin an immutable edition."""
    value = _name(value)
    qualified = re.fullmatch(r"(个人|实验室)(?:#([1-9][0-9]*))?/(.+)", value)
    if qualified:
        scope, revision, name = qualified.groups()
        return scope, int(revision) if revision else None, _name(name)
    if re.match(r"^(个人|实验室)(?:#[^/]*)?/", value):
        raise InputError("STYLE_REFERENCE", value, "请使用“实验室/名称”或“实验室#1/名称”等完整风格名。")
    return "个人", None, value


def _folder(scope, library):
    if library is None:
        raise ValueError("请使用当前选择的本地风格库。")
    personal = local_path(library)
    return local_path({"个人": personal, "实验室": personal.parent / "lab"}[scope])


def _editions(folder, name):
    """Later editions are append-only."""
    first = local_path(_path(folder, name))
    if not first.is_file():
        return {}
    editions = {1: first}
    for path in local_path(folder / "revisions").glob("*/" + first.name):
        tag = path.parent.name
        if re.fullmatch(r"[1-9][0-9]*", tag) and int(tag) >= 2:
            editions[int(tag)] = local_path(path)
    if len(editions) != max(editions):
        raise InputError("STYLE_HISTORY", name, "预设的修订记录不完整，请核对保存的文件。")
    return editions


def _builtin_profile(name):
    base = name if name in PRESET_IDS else "clean"
    _, values = _load_preset(base)
    if name == "汇报":
        for style, color in zip(values, TALK_COLORS, strict=True):
            style.update(color=color, symbol_size=8.0, line_width=2.0)
    return dict(schema=PROFILE_SCHEMA, name=name, base=base, legend_position="outside-right",
                slots=[dict(style=style) for style in values])


def _check_profile(profile, path=None):
    fields(profile, "个人风格", ("schema", "name", "base", "legend_position", "slots"), ("segments",))
    name = _name(profile["name"])
    if (profile["schema"] != PROFILE_SCHEMA or profile["base"] not in ("clean", "mono")
            or path is not None and (_builtin(name) or path != _path(path.parent, name))):
        raise InputError("PERSONAL_STYLE_FILE", name, "预设标识或基础风格有误。")
    check_position(profile["legend_position"], name)
    slots = profile["slots"]
    if not isinstance(slots, list) or len(slots) != 3:
        raise InputError("PERSONAL_STYLE_FILE", name, "预设应有三组可复用的系列外观。")
    pinned = set()
    for slot in slots:
        fields(slot, name, ("style",), ("sample",))
        if "sample" in slot:
            sample = identifier(slot["sample"], name)
            if sample in pinned:
                raise InputError("PERSONAL_STYLE_FILE", name, "同一样品被分配了多组外观。")
            pinned.add(sample)
        style = _attributes(slot["style"], name)
        if set(style) != STYLE_FIELDS or style["color"] == "#FFFFFF":
            raise InputError("PERSONAL_STYLE_FILE", name, "预设缺少系列属性，或线点使用了白色背景色。")
        slot["style"] = style
    if "segments" in profile:
        from .styles import segment_attributes
        if not isinstance(profile["segments"], dict):
            raise InputError("STYLE_OBJECT", name, "阶段风格须按原表阶段名分别给出。")
        profile["segments"] = {text_value(label, "阶段名"): segment_attributes(attrs, "阶段风格." + label)
                               for label, attrs in profile["segments"].items()}
    return profile


def _find_editions(selector, library):
    scope, edition, name = _selector(selector)
    editions = _editions(_folder(scope, library), name)
    if not editions:
        raise InputError("PERSONAL_STYLE_MISSING", selector, "找不到这个风格，可以先查看已有风格与所在库。")
    if edition is not None and edition not in editions:
        raise InputError("STYLE_REVISION_MISSING", selector, "没有这个修订版本，请查看该风格的历史。")
    return scope, name, editions, edition or max(editions)


def load_profile(name, *, library=None):
    selector = _name(name)
    builtin = _builtin(selector)
    if builtin:
        return _builtin_profile(builtin)
    _, _, editions, edition = _find_editions(selector, library)
    path = editions[edition]
    return _check_profile(read_json(path), path)


def list_presets(*, library=None):
    """Browsing styles, never creates a library."""
    names = list(BUILTINS)
    scopes = ("个人", "实验室")
    for scope in scopes:
        group = []
        for path in _folder(scope, library).glob("*.json"):
            name = _check_profile(read_json(path), path)["name"]
            qualified = scope != "个人" or re.match(r"^(个人|实验室)[#/]", name)
            group.append(f"{scope}/{name}" if qualified else name)
        names.extend(sorted(group, key=str.casefold))
    return names


def preset_history(selector, *, library=None):
    """Return exact references for replay, from newest to oldest."""
    selector = _name(selector)
    if _builtin(selector):
        return [selector + "（内置）"]
    scope, name, editions, _ = _find_editions(selector, library)
    return [f"{scope}#{number}/{name}" for number in sorted(editions, reverse=True)]


def preset_legend(name, *, library=None):
    return load_profile(name, library=library)["legend_position"]


def _plain_builtin(profile):
    # A captured clean/mono draft may include substantial customizations.
    return profile["name"] in PRESET_IDS and all("sample" not in slot for slot in profile["slots"])


def _selection(figures):
    # Dict insertion order gives the visible curve order, independent of hashed sample IDs.
    applicable = {}
    aliases = {}
    for figure in figures:
        for curve in figure["curves"]:
            sample = curve["sample"]
            if curve["kind"] not in APPLICABLE_FIELDS:
                raise InputError("PLOT_KIND", "kind", "请选择散点、折线或点线。")
            applicable.setdefault(sample, set()).update(APPLICABLE_FIELDS[curve["kind"]])
            for key in (sample, curve["label"]):
                aliases.setdefault(key, set()).add(sample)
    if not 1 <= len(applicable) <= 3:
        raise InputError("STYLE_SAMPLES", "样品", "一份风格可分配给一至三个样品。")
    return applicable, aliases


def _assign(profile, samples):
    if _plain_builtin(profile):
        # Keep the accepted clean/mono ordering of earlier tasks.
        return {sample: i for i, sample in enumerate(sorted(samples))}
    assigned = {slot["sample"]: i for i, slot in enumerate(profile["slots"])
                if slot.get("sample") in samples}
    remaining = iter(i for i in range(3) if i not in assigned.values())
    for sample in samples:
        if sample not in assigned:
            assigned[sample] = next(remaining)
    return assigned


def style_for_figures(name, figures, *, defaults=None, samples=None, library=None, snapshot=None):
    """Expand a named style, then apply one-use global and per-sample overrides.

    Keys in samples may be sample IDs or unambiguous visible legend labels.
    The returned style can be compiled again without the personal style library.
    """
    profile = load_profile(name, library=library) if snapshot is None else _check_profile(snapshot)
    applicable, aliases = _selection(figures)
    global_attrs = _attributes({} if defaults is None else defaults, "style.defaults")
    if samples is None:
        samples = {}
    if not isinstance(samples, dict):
        raise InputError("STYLE_OBJECT", "style.samples", "请按样品或图例名给出本次调整。")
    one_use = {}
    for key, attrs in samples.items():
        matched = aliases.get(key, set())
        if len(matched) != 1:
            raise InputError("STYLE_SAMPLE", str(key), "此名称没有唯一对应当前样品，请使用明确的样品名。")
        sample = next(iter(matched))
        if sample in one_use:
            raise InputError("STYLE_SAMPLE", key, "同一样品有两组调整，请合并。")
        one_use[sample] = _attributes(attrs, f"style.samples.{sample}")
    result = {"preset": profile["base"]}
    if global_attrs:
        result["defaults"] = global_attrs
    overrides = {}
    for sample, index in _assign(profile, applicable).items():
        slot = {}
        if not _plain_builtin(profile):
            slot = {k: v for k, v in profile["slots"][index]["style"].items()
                    if k in applicable[sample] and k not in global_attrs}
        slot.update(one_use.get(sample, {}))
        if slot:
            overrides[sample] = slot
    if overrides:
        result["samples"] = overrides
    if profile.get("segments"):
        active = {}
        for figure in figures:
            for curve in figure["curves"]:
                label = curve.get("segment")
                if label in profile["segments"]:
                    active.setdefault(label, set()).update(APPLICABLE_FIELDS[curve["kind"]])
        for label, applicable_fields in active.items():
            attrs = {key: value for key, value in profile["segments"][label].items() if key in applicable_fields}
            if attrs:
                result.setdefault("segments", {})[label] = attrs
    resolve_style(result, list(applicable), figures)
    return result


def capture_profile(plan, *, source=None, defaults=None, library=None):
    """Freeze all three slots, including attributes hidden by the current plot type."""
    name = plan.get("style_name", plan["styles"]["preset"])
    if source is None:
        # Older drafts may predate full snapshots. All attributes visible in their
        # plots are still exact; the bundled base supplies otherwise unknown defaults.
        try:
            source = load_profile(name, library=library)
        except InputError as exc:
            if exc.code != "PERSONAL_STYLE_MISSING":
                raise
            source = load_profile(plan["styles"]["preset"], library=library)
    figures = plan["data"]["figures"]
    applicable, _ = _selection(figures)
    assigned = _assign(source, applicable)
    global_attrs = _attributes({} if defaults is None else defaults, "style.defaults")
    slots = []
    for sample, active_fields in applicable.items():
        # Inactive fields (e.g. marker shape on a plain line) retain the source style.
        style = {**source["slots"][assigned[sample]]["style"], **global_attrs}
        effective = plan["styles"]["samples"][sample]
        style.update({k: effective[k] for k in effective if k in active_fields})
        slots.append(dict(sample=sample, style=style))
    for i, slot in enumerate(source["slots"]):
        if i not in assigned.values():
            slots.append({**slot, "style": {**slot["style"], **global_attrs}})
    profile = dict(schema=PROFILE_SCHEMA, name=name, base=source["base"],
                   legend_position=figures[0].get("legend_position", "outside-right"), slots=slots)
    segments = {label: attrs.copy() for label, attrs in source.get("segments", {}).items()}
    for label, attrs in plan["styles"].get("segments", {}).items():
        segments.setdefault(label, {}).update(attrs)
    if segments:
        profile["segments"] = segments
    return _check_profile(profile)


def save_preset(name, plan, *, source_name=None, defaults=None, library=None, snapshot=None, update_from=None):
    """Create a profile or append one edition conditional on the expected current edition."""
    scope, edition, name = _selector(name)
    if edition is not None:
        raise InputError("STYLE_READ_ONLY", name, "已编号版本只读。另存到个人或实验室库可建立新风格。")
    from .planner import plain_label
    plain_label(name, "风格名")
    if _builtin(name):
        raise InputError("PERSONAL_STYLE_EXISTS", name, "该名称已用于内置风格，请另取一个名字。")
    folder = _folder(scope, library)
    editions = _editions(folder, name)
    path = _path(folder, name)
    if update_from is None:
        if editions:
            raise InputError("PERSONAL_STYLE_EXISTS", name, "这个风格已经存在。可以另存新名，或明确更新当前版本。")
    else:
        if type(update_from) is not int or update_from < 1 or not editions or update_from != max(editions):
            current = max(editions, default=0)
            raise InputError("STYLE_REVISION_CONFLICT", name, f"当前版本为 {current}。请核对预设历史后更新。")
        path = folder / "revisions" / str(update_from + 1) / path.name
    # A pinned selector must fit the same visible-text contract used in an ordinary plotting plan.
    plain_label(f"{scope}#{(update_from or 0) + 1}/{name}", "版本化风格名")
    if snapshot is None:
        source = load_profile(source_name, library=library) if source_name else None
        snapshot = capture_profile(plan, source=source, defaults=defaults, library=library)
    profile = _check_profile({**snapshot, "name": name}, path)
    path = local_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
    try:
        temp.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Windows rename and POSIX hard link both publish without replacing a concurrent save.
        if os.name == "nt":
            temp.rename(path)
        else:
            os.link(temp, path)
    except FileExistsError as exc:
        code = "PERSONAL_STYLE_EXISTS" if update_from is None else "STYLE_REVISION_CONFLICT"
        raise InputError(code, name, "这个风格或版本已经存在。请核对预设历史。") from exc
    finally:
        temp.unlink(missing_ok=True)
    return path
