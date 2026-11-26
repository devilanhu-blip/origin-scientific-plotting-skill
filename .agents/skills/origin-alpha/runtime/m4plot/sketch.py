"""Offline PNG sketches of compiled plans. This module never opens an Origin session."""

from decimal import Decimal, ROUND_CEILING
from math import hypot
import os
from pathlib import Path
import tempfile

from .common import figure_title
from .styles import curve_style


INK = "#172C3F"
MUTED = "#526474"
GRID = "#DFE5EA"


def _pillow():
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


class _Axis:
    """Normalize in decimal space so ±1e308 and tiny, nearly equal readings plot correctly."""

    def __init__(self, minimum, maximum):
        lo, hi = Decimal(str(minimum)), Decimal(str(maximum))
        if hi == lo:
            pad = abs(lo) / 20 or Decimal(1)
        else:
            pad = (hi - lo) / 24
        span = hi - lo
        self.offset = lo if span and abs(lo) > span * 10000 else Decimal(0)
        magnitude = max(abs(lo - self.offset), abs(hi - self.offset), pad)
        exponent = magnitude.adjusted()
        self.exponent = exponent if exponent >= 5 or exponent <= -4 else 0
        self.scale = Decimal(10) ** self.exponent
        self.low = (lo - self.offset - pad) / self.scale
        self.high = (hi - self.offset + pad) / self.scale
        interval = (self.high - self.low) / 5
        order = Decimal(10) ** interval.adjusted()
        step = next(k * order for k in map(Decimal, ("1", "2", "2.5", "5", "10")) if k * order >= interval)
        value = (self.low / step).to_integral_value(rounding=ROUND_CEILING) * step
        self.ticks = []
        while value <= self.high:
            self.ticks.append((self._fraction(value), format(value.normalize() if value else Decimal(0), "f")))
            value += step

    def _fraction(self, scaled):
        return float((scaled - self.low) / (self.high - self.low))

    def position(self, reading):
        return self._fraction((Decimal(str(reading)) - self.offset) / self.scale)

    def caption(self, meta):
        label = f"{meta['quantity']} / {meta['unit']}"
        if self.exponent or self.offset:
            formula = "刻度" + (f" × 10^{self.exponent}" if self.exponent else "")
            if self.offset:
                sign = " + " if self.offset > 0 else " − "
                formula += sign + str(abs(self.offset).normalize())
            label += f"  （实际读数 = {formula}）"
        return label


def _wrap(text, font, width):
    if font.getlength(text) <= width:
        return [text]
    lines, start = [], 0
    while start < len(text):
        lo, hi = start + 1, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.getlength(text[start:mid]) <= width:
                lo = mid
            else:
                hi = mid - 1
        end = lo
        if end < len(text) and text[end - 1].isascii() and text[end].isascii():
            split = text.rfind(" ", start, end)
            if split > start:
                end = split + 1
        lines.append(text[start:end].rstrip())
        start = end
    return lines


def _patterned_line(draw, points, color, width, pattern):
    if pattern == "solid":
        draw.line(points, fill=color, width=width)
        return
    unit = max(2, width)
    on, off = (4 * unit, 2 * unit) if pattern == "dash" else (unit, 2 * unit)
    period = on + off
    phase = 0.0
    for (x, y), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x, y2 - y
        length = hypot(dx, dy)
        if not length:
            continue
        # Continue the pattern across vertices and through reversals.
        start = -phase
        while start < length:
            lo = max(0, start)
            hi = min(start + on, length)
            if hi > lo:
                draw.line([(x + dx * lo / length, y + dy * lo / length),
                           (x + dx * hi / length, y + dy * hi / length)], fill=color, width=width)
            start += period
        phase = (phase + length) % period


def _glyph(draw, points, kind, style):
    color = style["color"]
    if kind in ("line", "linesymbol"):
        width = max(1, round(min(style["line_width"], 12) * 2))
        _patterned_line(draw, points, color, width, style["line"])
    if kind != "line":
        radius = max(2, round(min(style["symbol_size"], 28) * 0.95))
        shape = draw.ellipse if style["symbol"] == "circle" else draw.rectangle
        fill = color if style["fill"] == "solid" else "#FFFFFF"
        for x, y in points:
            shape((x-radius, y-radius, x+radius, y+radius), fill=fill, outline=color, width=2)


def _error_bounds(ys, magnitudes):
    # Compute in the same decimal coordinate system as the axes. Endpoints are
    # preview coordinates only. The worksheet retains its original Y and error.
    bounds = []
    for y, magnitude in zip(ys, magnitudes, strict=True):
        centre, distance = Decimal(str(y)), Decimal(str(magnitude))
        bounds.append((centre - distance, centre + distance))
    return bounds


def _draw_errors(draw, points, bounds, y_pixel, color):
    for (x, _), (low, high) in zip(points, bounds, strict=True):
        if high == low:
            continue
        top, bottom = y_pixel(high), y_pixel(low)
        draw.line((x, top, x, bottom), fill=color, width=2)
        for y in (top, bottom):
            draw.line((x-5, y, x+5, y), fill=color, width=2)


def _figure_image(plan, fig, pil, fonts):
    Image, ImageDraw, _ = pil
    axis_font, tick_font, title_font, badge_font = fonts
    data, styles = plan["data"], plan["styles"]["samples"]
    values = {col["header"]: col["values"] for col in data["columns"]}
    selected = []
    definitions = {}
    for curve in fig["curves"]:
        start, end = curve["rows"]
        xs, ys = (values[curve[axis]][start-1:end] for axis in ("x", "y"))
        bounds = None
        if "y_error" in curve:
            error = curve["y_error"]
            bounds = _error_bounds(ys, values[error["column"]][start-1:end])
            definitions.setdefault(error["definition"], []).append(curve["label"])
        selected.append((xs, ys, bounds))
    x_axis = _Axis(min(min(xs) for xs, _, _ in selected), max(max(xs) for xs, _, _ in selected))
    y_axis = _Axis(min(min(lo for lo, _ in bounds) if bounds else min(ys) for _, ys, bounds in selected),
                   max(max(hi for _, hi in bounds) if bounds else max(ys) for _, ys, bounds in selected))
    position = fig.get("legend_position", "outside-right")
    outside = position == "outside-right"
    entries = []
    if position != "hidden":
        for curve in fig["curves"]:
            entries.append((_wrap(curve["label"], tick_font, 310 if outside else 350), curve))
    legend_width = 0
    legend_height = 0
    if entries:
        legend_width = 81 + int(max(tick_font.getlength(s) for lines, _ in entries for s in lines))
        legend_height = 14 + sum(len(lines) * 28 + 8 for lines, _ in entries)

    plot_height = max(490, legend_height + 52)
    y_lines = _wrap(y_axis.caption(fig["axes"]["y"]), axis_font, plot_height - 20)
    left = round(57 + len(y_lines) * 29 + max(tick_font.getlength(t) for _, t in y_axis.ticks))
    plot_width = max(760, 1210 - left - (legend_width + 32 if outside else 0))
    right = left + plot_width
    width = right + 46 + (legend_width + 32 if outside else 0)
    titles = _wrap(figure_title(data, fig), title_font, width - 86)
    top = 90 + len(titles) * 46 + 15
    bottom = top + plot_height
    x_lines = _wrap(x_axis.caption(fig["axes"]["x"]), axis_font, plot_width)
    clipped_size = any(
        (curve["kind"] != "scatter" and styles[curve["sample"]]["line_width"] > 12)
        or (curve["kind"] != "line" and styles[curve["sample"]]["symbol_size"] > 28)
        for curve in fig["curves"])
    notes = []
    for definition, labels in definitions.items():
        prefix = "" if len(labels) == len(selected) else "、".join(labels) + "的"
        notes.extend(_wrap(f"{prefix}误差棒表示{definition}", tick_font, width - left - 40))
    footer_y = bottom + 82 + len(x_lines) * 29
    height = footer_y + 29 * len(notes) + (34 if clipped_size else 0)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 51), fill="#EAF2F6")
    draw.text((30, 25), "OFFLINE_PREVIEW · 离线预览", font=badge_font, fill="#284B5C", anchor="lm")
    source_note = "模拟数据" if data["kind"] == "SIMULATED" else "实测数据"
    draw.text((width-30, 25), source_note, font=badge_font, fill="#284B5C", anchor="rm")
    for j, title in enumerate(titles):
        draw.text((width/2, 90+j*46), title, font=title_font, fill=INK, anchor="mm")
    for fraction, label in y_axis.ticks:
        y = bottom - round(fraction * plot_height)
        draw.line((left, y, right, y), fill=GRID)
        draw.line((left-6, y, left, y), fill=INK, width=2)
        draw.text((left-12, y), label, font=tick_font, fill=MUTED, anchor="rm")
    for fraction, label in x_axis.ticks:
        x = left + round(fraction * plot_width)
        draw.line((x, bottom, x, bottom+6), fill=INK, width=2)
        draw.text((x, bottom+12), label, font=tick_font, fill=MUTED, anchor="mt")
    draw.line([(left, top), (left, bottom), (right, bottom)], fill=INK, width=2)
    for j, line in enumerate(x_lines):
        draw.text((left+plot_width/2, bottom+59+j*29), line, font=axis_font, fill=INK, anchor="mm")
    # Render a wrapped vertical caption as one rotated block so long units remain legible.
    rotated = Image.new("RGB", (plot_height, len(y_lines)*29+8), "white")
    caption = ImageDraw.Draw(rotated)
    for j, line in enumerate(y_lines):
        caption.text((plot_height/2, 18+j*29), line, font=axis_font, fill=INK, anchor="mm")
    image.paste(rotated.transpose(Image.Transpose.ROTATE_90), (10, top))
    def y_pixel(y):
        return bottom - round(y_axis.position(y) * plot_height)

    for (xs, ys, bounds), curve in zip(selected, fig["curves"], strict=True):
        points = [(left + round(x_axis.position(x) * plot_width), y_pixel(y))
                  for x, y in zip(xs, ys, strict=True)]
        style = curve_style(plan["styles"], curve)
        if bounds:
            _draw_errors(draw, points, bounds, y_pixel, style["color"])
        _glyph(draw, points, curve["kind"], style)

    if entries:
        x = right + 24 if outside else (left + 16 if position.endswith("-left") else right-legend_width-16)
        y = bottom-legend_height-16 if position.startswith("lower-") else top + (0 if outside else 16)
        if not outside:
            draw.rectangle((x, y, x+legend_width, y+legend_height), fill="white", outline=GRID)
        y += 12
        for lines, curve in entries:
            style, kind = curve_style(plan["styles"], curve), curve["kind"]
            if kind != "scatter":
                _glyph(draw, [(x+10, y+11), (x+54, y+11)], "line", style)
            if kind != "line":
                _glyph(draw, [(x+32, y+11)], "scatter", style)
            for line in lines:
                draw.text((x+66, y+11), line, font=tick_font, fill=INK, anchor="lm")
                y += 28
            y += 8
    for index, line in enumerate(notes):
        draw.text((left, footer_y + index * 29), line, font=tick_font, fill=MUTED, anchor="lt")
    if clipped_size:
        draw.text((width/2, height-24), "超大线宽或点径已按预览画布上限显示", font=tick_font, fill=MUTED, anchor="mm")
    return image


def write_previews(plan, folder, font_paths):
    """Write a fresh PNG per figure to folder and return its paths, in figure order."""
    figures = plan["data"]["figures"]
    if not figures:
        raise ValueError("需要至少一张图才能保存离线预览。")
    folder = Path(folder)
    paths = [folder / f"preview-{i}.png" for i in range(1, len(figures)+1)]
    if any(p.exists() for p in paths):
        raise FileExistsError("草稿目录已经有同名预览图，请选择新目录。")
    pil = _pillow()
    regular, bold = font_paths
    fonts = [pil[2].truetype(str(face), size) for face, size in (
        (regular, 22), (regular, 18), (bold, 32), (bold, 18))]
    folder.mkdir(parents=True, exist_ok=True)
    created = []
    with tempfile.TemporaryDirectory(dir=folder) as staging:
        for fig, path in zip(figures, paths, strict=True):
            with _figure_image(plan, fig, pil, fonts) as image:
                image.save(Path(staging) / path.name, format="PNG")
        try:
            for path in paths:
                staged = Path(staging) / path.name
                if os.name == "nt":
                    staged.rename(path)
                else:
                    os.link(staged, path)
                created.append(path)
        except OSError:
            for path in created:
                path.unlink()
            raise
    return paths
