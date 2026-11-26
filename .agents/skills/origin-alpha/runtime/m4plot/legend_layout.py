"""Legend positions for the offline planner."""

from .common import InputError


POSITIONS = {
    "outside-right": "绘图区右侧（图外）",
    "upper-left": "图内左上角",
    "upper-right": "图内右上角",
    "lower-left": "图内左下角",
    "lower-right": "图内右下角",
    "hidden": "隐藏",
}


def check_position(value, field):
    if not isinstance(value, str) or value not in POSITIONS:
        raise InputError("LEGEND_POSITION", field, "可选择图外右侧、图内四角或隐藏图例。")
    return value
