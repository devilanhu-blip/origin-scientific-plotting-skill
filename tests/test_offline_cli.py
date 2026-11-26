"""Exercise the public entry point with synthetic inputs and fresh, isolated state."""

import csv
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from offline_cli import CSV, DEFINITION, ERROR, PROFILES, X, Y, example_options, read_json, run_cli


class OfflineCLI(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(prefix="origin-alpha-")
        self.addCleanup(scratch.cleanup)
        self.cwd = Path(scratch.name) / "独立 副本"
        self.cwd.mkdir()
        self.state = self.cwd / "离线 状态"
        self.csv = self.cwd / CSV.name
        shutil.copyfile(CSV, self.csv)

    def invoke(self, *args, error=None):
        result = run_cli(self.cwd, self.state, *args)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(result.stdout.strip(), result.stdout)
        self.assertRegex(result.stderr, error)

    def draft(self, source=None, *options, preset="clean"):
        info = self.invoke("inspect", source or self.csv)
        return self.invoke("draft", source or self.csv, *example_options(), "--preset", preset,
                           "--expected-sha256", info["sha256"], *options)

    def plan(self, receipt):
        plan = read_json(Path(receipt["draft"]) / "plan.json")
        canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(receipt["plan_digest"], sha256(canonical.encode("utf-8")).hexdigest())
        self.assertFalse(plan["native_authorized"])
        self.assertFalse(plan["native_observed"])
        return plan

    def rewrite(self, name, *, header=None, cells=()):
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        if header:
            before, after = header
            rows[0][rows[0].index(before)] = after
        for number, column, value in cells:
            rows[number][rows[0].index(column)] = value
        path = self.cwd / f"SIMULATED_{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows(rows)
        return path

    def test_inspect_and_plan_preserve_source_rows_values_and_half_widths(self):
        raw = self.csv.read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = list(reader)
        info = self.invoke("inspect", self.csv.name)
        self.assertEqual(info["headers"], reader.fieldnames)
        self.assertEqual(info["row_count"], 8)
        self.assertEqual(info["sha256"], sha256(raw).hexdigest())
        self.assertEqual(info["preview"], [list(row.values()) for row in rows[:3]])
        self.assertFalse(self.state.exists())

        receipt = self.draft(self.csv.name)
        plan = self.plan(receipt)
        data = plan["data"]
        self.assertEqual(receipt["status"], "OFFLINE_PREVIEW")
        self.assertEqual(data["kind"], "SIMULATED")
        self.assertEqual(data["source_name"], self.csv.name)
        self.assertEqual(data["source_sha256"], info["sha256"])
        self.assertEqual(data["row_count"], len(rows))
        columns = {column["header"]: column for column in data["columns"]}
        self.assertEqual(set(columns), {X, Y, ERROR})
        for header, unit in [(X, "K"), (Y, "mV"), (ERROR, "mV")]:
            self.assertEqual(columns[header]["unit"], unit)
            self.assertEqual(columns[header]["tokens"], [row[header] for row in rows])
            self.assertEqual(columns[header]["values"], [float(row[header]) for row in rows])

        figure, = data["figures"]
        self.assertEqual(figure["axes"], {"x": {"quantity": "温度", "unit": "K"},
                                           "y": {"quantity": "电压", "unit": "mV"}})
        self.assertEqual([(curve["segment"], curve["rows"]) for curve in figure["curves"]],
                         [("升温", [1, 4]), ("降温", [5, 8])])
        mapped = plan["object_map"]["figures"][figure["id"]]["curves"]
        endpoints = []
        for plot, curve in zip((1, 3), figure["curves"], strict=True):
            self.assertEqual((curve["x"], curve["y"]), (X, Y))
            self.assertEqual(curve["y_error"]["column"], ERROR)
            self.assertEqual(curve["y_error"]["definition"], DEFINITION)
            mapping = mapped[curve["id"]]
            self.assertEqual((mapping["plot"], mapping["error_plot"]), (plot, plot + 1))
            self.assertEqual(mapping["rows"], curve["rows"])
            self.assertEqual(mapping["y_error_column"], 3)
            start, end = curve["rows"]
            for center, width in zip(columns[Y]["values"][start-1:end], columns[ERROR]["values"][start-1:end], strict=True):
                center, width = Decimal(str(center)), Decimal(str(width))
                endpoints.append((str(center - width), str(center + width)))
        self.assertEqual(endpoints, [("1.06", "1.18"), ("1.27", "1.43"), ("1.41", "1.51"), ("1.70", "1.92"),
                                     ("1.67", "1.85"), ("1.46", "1.60"), ("1.23", "1.31"), ("1.00", "1.12")])
        self.assertEqual(self.csv.read_bytes(), raw)

    def test_presets_only_change_appearance(self):
        self.assertEqual(self.invoke("presets")["presets"], list(PROFILES))
        self.assertFalse(self.state.exists())
        expected = {"clean": ("#0072B2", 1.1, 5.0), "mono": ("#000000", 1.1, 5.0),
                    "汇报": ("#174C80", 2.0, 8.0)}
        data = object_map = science_digest = None
        all_pixels = set()
        for preset in PROFILES:
            with self.subTest(preset=preset):
                receipt = self.draft(None, "--segment", "降温", "symbol", "square", preset=preset)
                plan = self.plan(receipt)
                self.assertEqual(receipt["style_name"], preset)
                if data is None:
                    data, object_map, science_digest = plan["data"], plan["object_map"], receipt["science_digest"]
                self.assertEqual(plan["data"], data)
                self.assertEqual(plan["object_map"], object_map)
                self.assertEqual(receipt["science_digest"], science_digest)
                self.assertRegex(receipt["science_digest"], r"^[0-9a-f]{64}$")
                sample_style, = plan["styles"]["samples"].values()
                self.assertEqual(tuple(sample_style[key] for key in ("color", "line_width", "symbol_size")), expected[preset])
                self.assertEqual((sample_style["line"], sample_style["symbol"], sample_style["fill"]),
                                 ("solid", "circle", "solid"))
                self.assertEqual(plan["styles"]["segments"]["降温"],
                                 {"line": "dash", "symbol": "square", "fill": "open"})
                self.assertEqual(plan["data"]["figures"][0]["legend_position"], "outside-right")
                image_path, = receipt["previews"]
                with Image.open(image_path) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertGreater(image.width, 500)
                    self.assertGreater(image.height, 300)
                    all_pixels.add(sha256(image.tobytes()).hexdigest())
        self.assertEqual(len(all_pixels), len(PROFILES))

    def test_revise_save_two_editions_and_pin_first(self):
        original = self.draft()
        original_plan = self.plan(original)
        revised = self.invoke("draft", original["draft"], "--visibility", "managed",
                              "--segment", "降温", "line", "dot", "--segment", "降温", "symbol", "square")
        version1 = self.plan(revised)
        self.assertEqual(version1["data"], original_plan["data"])
        self.assertEqual(version1["object_map"], original_plan["object_map"])
        self.assertEqual(version1["styles"]["samples"], original_plan["styles"]["samples"])
        self.assertEqual(version1["styles"]["segments"]["降温"], {"line": "dot", "symbol": "square", "fill": "open"})
        self.assertEqual(revised["science_digest"], original["science_digest"])
        self.assertNotEqual(revised["plan_digest"], original["plan_digest"])

        name = "实验室/热循环"
        self.invoke("save-style", revised["draft"], name)
        self.invoke("save-style", revised["draft"], name, error="PERSONAL_STYLE_EXISTS")
        latest = self.invoke("draft", revised["draft"], "--visibility", "managed", "--segment", "降温", "line", "dash")
        version2 = self.plan(latest)
        self.invoke("save-style", latest["draft"], name, "--update-from", "1")
        self.invoke("save-style", latest["draft"], name, "--update-from", "1", error="STYLE_REVISION_CONFLICT")
        pinned_name = "实验室#1/热循环"
        self.assertEqual(set(self.invoke("history", name)["versions"]), {pinned_name, "实验室#2/热循环"})
        self.assertIn(name, self.invoke("presets")["presets"])

        for preset, expected in ((pinned_name, version1), (name, version2)):
            with self.subTest(preset=preset):
                picked = self.draft(preset=preset)
                picked_plan = self.plan(picked)
                self.assertEqual(picked_plan["styles"], expected["styles"])
                self.assertEqual(picked_plan["data"], original_plan["data"])
                self.assertEqual(picked["science_digest"], original["science_digest"])
        replay = self.invoke("preview", original["draft"], "--visibility", "managed")
        self.assertEqual(replay["plan_digest"], original["plan_digest"])

    def test_rejects_historically_ambiguous_error_definitions(self):
        # The parent packaging review observed all three being accepted before the guard was added.
        for name, definition in (("标准差 [mV]", "重复实验得到的标准差"),
                                 ("SEM [mV]", "mean ± SEM"), (ERROR, "不知道定义")):
            with self.subTest(error_column=name, definition=definition):
                source = self.rewrite("ambiguous", header=(ERROR, name))
                self.invoke("draft", source, *example_options(error=name, definition=definition), error="ERROR_DEFINITION")

    def test_rejects_invalid_sources_and_unsupported_bindings(self):
        mismatched = self.rewrite("unit", header=(ERROR, "电压绝对误差 [V]"))
        self.invoke("draft", mismatched, *example_options(error="电压绝对误差 [V]"), error="ERROR_UNIT")
        missing_unit = self.rewrite("missing_unit", header=(Y, "电压"))
        self.invoke("draft", missing_unit, *example_options(y="电压"), error="UNIT_UNKNOWN")
        negative = self.rewrite("negative", cells=((1, ERROR, "-0.01"),))
        self.invoke("draft", negative, *example_options(), error="ERROR_NEGATIVE")
        interleaved = self.rewrite("interleaved", cells=((2, "阶段", "降温"),))
        self.invoke("draft", interleaved, *example_options(), error="BRANCH_INTERLEAVED")
        third_branch = self.rewrite("three", cells=((7, "阶段", "回程"), (8, "阶段", "回程")))
        self.invoke("draft", third_branch, *example_options(), error="两条")
        self.invoke("draft", self.csv, *example_options(error="缺失误差 [mV]"), error="缺失误差")
        measured = example_options()
        measured[measured.index("SIMULATED")] = "MEASURED"
        self.invoke("draft", self.csv, *measured, error="SIMULATED")
        without_visibility = example_options()
        index = without_visibility.index("--visibility")
        del without_visibility[index:index + 2]
        self.invoke("draft", self.csv, *without_visibility, error="--visibility")
        self.assertFalse(list(self.state.glob("drafts/*")))

    def test_source_digest_and_draft_files_are_rechecked(self):
        known = self.invoke("inspect", self.csv)["sha256"]
        receipt = self.draft()
        folder = Path(receipt["draft"])
        managed = ("--visibility", "managed")
        self.invoke("draft", folder, *managed, "--x", Y, error="原 CSV|原始 CSV")
        for filename in ("task.json", "plan.json", "style.json"):
            with self.subTest(mutated=filename):
                path = folder / filename
                original = path.read_bytes()
                try:
                    payload = read_json(path)
                    payload["schema"] = "modified/1"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    self.invoke("preview", folder, *managed, error="改变|变更|校验|摘要|changed|mismatch|SCHEMA")
                finally:
                    path.write_bytes(original)
        self.assertEqual(self.invoke("preview", folder, *managed)["plan_digest"], receipt["plan_digest"])
        self.csv.write_bytes(self.csv.read_bytes().replace(b"1.12", b"1.13", 1))
        self.invoke("draft", self.csv, *example_options(), "--expected-sha256", known, error="SOURCE_CHANGED")
        self.invoke("preview", folder, *managed, error="SOURCE_CHANGED|改变|变更")
        self.invoke("save-style", folder, "实验室/过期草稿", error="SOURCE_CHANGED|改变|变更")
        self.assertEqual(self.invoke("presets")["presets"], list(PROFILES))


if __name__ == "__main__":
    unittest.main()
