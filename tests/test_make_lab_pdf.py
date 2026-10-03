"""Regression checks for input boundaries, statistics and real TeX parsing."""
import importlib.util
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_lab_pdf.py"
spec = importlib.util.spec_from_file_location("lab", SCRIPT)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rows = [{"x": float(x), "y": y, "w": float(x + 1)} for x, y in enumerate([1., 3.2, 4.8, 7.3])]

    def tearDown(self):
        self.temp.cleanup()

    def csv(self, text):
        target = self.root / "data.csv"
        target.write_text(text, encoding="utf-8")
        return lab.read_csv(target)

    def fit(self, **extra):
        return lab.make_fit({"x": "x", "y": "y", **extra}, self.rows)

    def test_relative_weight_scale_invariance_linear_and_formula(self):
        for model in [{}, {"model": "formula", "formula": "a+b*x", "parameters": {"a": 0, "b": 1}}]:
            original = self.fit(weight_key="w", **model)
            scaled = lab.make_fit({"x": "x", "y": "y", "weight_key": "w", **model},
                                  [{**row, "w": 10 * row["w"]} for row in self.rows])
            for key in ("values", "errors"):
                for left, right in zip(original[key], scaled[key]):
                    self.assertAlmostEqual(left, right, places=7)
            self.assertAlmostEqual(original["errors"][0], 0.31464265445, places=7)
            self.assertAlmostEqual(original["errors"][1], 0.14071247279, places=7)

    def test_absolute_uncertainty_covariance(self):
        rows = [{"x": float(x), "y": 1 + 2.0 * x, "sigma": 0.5} for x in range(4)]
        result = lab.make_fit({"x": "x", "y": "y", "sigma_key": "sigma"}, rows)
        self.assertAlmostEqual(result["errors"][1], math.sqrt(0.25 / 5))
        larger = lab.make_fit({"x": "x", "y": "y", "sigma_key": "sigma"}, [{**r, "sigma": 1.0} for r in rows])
        self.assertAlmostEqual(larger["errors"][1], 2 * result["errors"][1])

    def test_rmse_and_residual_standard_error_are_distinct(self):
        result = self.fit()
        self.assertAlmostEqual(result["rmse"], math.sqrt(result["sse"] / 4))
        self.assertAlmostEqual(result["residual_standard_error"], math.sqrt(result["sse"] / 2))

    def test_fixed_parameters_participate_in_fit_and_curve(self):
        rows = [{"x": float(x), "y": 2 * x + 1.0} for x in range(4)]
        fit = {"x": "x", "y": "y", "model": "formula", "formula": "A*x+k", "parameters": {"A": 1}, "fixed_parameters": {"k": 1}}
        result = lab.make_fit(fit, rows)
        self.assertAlmostEqual(result["values"][0], 2, places=6)
        xs, ys = lab.curve_samples(fit, result)
        self.assertAlmostEqual(ys[-1], 2 * xs[-1] + 1, places=6)
        self.assertEqual(result["names"], ["A"])

    def test_theory_curves_do_not_require_floating_parameters(self):
        for model in ("theory", "formula"):
            result = self.fit(model=model, formula="k*x+1", fixed_parameters={"k": 2})
            self.assertEqual(result["fit_status"]["status"], "theory")
            self.assertEqual(result["values"], [])

    def test_curve_padding_does_not_extend_sqrt_domain(self):
        rows = [{"x": x, "y": 2 * math.sqrt(x)} for x in [0., 1., 4., 9.]]
        fit = {"x": "x", "y": "y", "model": "formula", "formula": "A*sqrt(x)", "parameters": {"A": 2}, "domain": [0, 9]}
        result = lab.make_fit(fit, rows)
        xs, ys = lab.curve_samples(fit, result)
        self.assertEqual(min(xs), 0)
        self.assertEqual(ys[0], 0)
        lab.tex_document(lab.validate_config({"fit": fit}, ["x", "y"]), rows, {"fit": fit}, "fit", result)

    def test_nonfinite_csv_and_parameter_values_are_rejected(self):
        for value in ["nan", "inf", "-inf", "1e309"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Row 3, column y"):
                self.csv("x,y\n0,1\n1," + value + "\n")
        with self.assertRaises(ValueError):
            self.fit(model="formula", formula="A*x", parameters={"A": math.nan})

    def test_csv_preserves_decimal_spelling_and_normalizes_headers(self):
        keys, rows = self.csv(" x , y \n0.00,1.2300\n1.00,2.3400\n")
        self.assertEqual(keys, ["x", "y"])
        tex = lab.tex_document(lab.validate_config({}, keys), rows, {}, "table")
        self.assertIn("0.00 & 1.2300", tex)

    def test_duplicate_missing_extra_and_unsafe_csv_headers_fail(self):
        for source in ["x,x\n1,2\n", "x,y\n1\n", "x,y\n1,2,3\n", "x,y\n1,\n", "\\input{marker.txt},y\n1,2\n"]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.csv(source)

    def test_plain_tex_commands_are_literal_text(self):
        rendered = lab.display_tex(r"A&B 50% \input{marker.txt}")
        self.assertIn(r"A\&B 50\%", rendered)
        self.assertIn(r"\textbackslash{}input\{marker.txt\}", rendered)
        self.assertNotIn(r"\input{", rendered)

    def test_math_markup_rejects_file_and_macro_commands(self):
        for text in [r"$\input{marker.txt}$", r"$\csname input\endcsname$", r"$^^5cinput$", r"$a & b$", "$a}$"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                lab.display_tex(text)
        self.assertEqual(lab.display_tex(r"$T\,/\,\mathrm{K}$"), r"$T\,/\,\mathrm{K}$")

    def test_formula_ast_blocks_non_math_operations(self):
        for expression in ["x.__class__", "x[0]", "(lambda: 1)()", "open(x)"]:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                lab.safe_expression(expression, [])

    def test_parameter_names_cannot_shadow_math_or_x(self):
        for name in ["x", "pi", "sin"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.fit(model="formula", formula="x", parameters={name: 1})

    def test_unidentifiable_fit_is_rejected(self):
        rows = [{"x": float(x), "y": float(4 * x)} for x in [1, 2, 3, 4]]
        with self.assertRaisesRegex(ValueError, "identifiable"):
            lab.make_fit({"x": "x", "y": "y", "model": "formula", "formula": "a**2*x", "parameters": {"a": 0}}, rows)

    def test_iteration_exhaustion_is_not_success(self):
        with self.assertRaisesRegex(ValueError, "did not converge"):
            self.fit(model="formula", formula="a*exp(b*x)", parameters={"a": 1, "b": 0.01}, max_iterations=1)

    def test_bounds_and_positive_decay_fit(self):
        rows = [{"x": float(x), "y": 3 * math.exp(-0.4 * x) + 1} for x in range(8)]
        fit = {"x": "x", "y": "y", "model": "formula", "formula": "A*exp(-k*x)+c", "parameters": {"A": 2, "k": 0.2, "c": 0.5}, "bounds": {"k": [0, None]}}
        result = lab.make_fit(fit, rows)
        for actual, expected in zip(result["values"], [3, 0.4, 1]):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertEqual(result["fit_status"]["status"], "converged")

    def test_unknown_fields_and_unsupported_options_fail(self):
        for extra in [{"colour": "red"}, {"result_position": "north west"}, {"curve_color": "red,other=1"},
                      {"x_range": [2, 1]}, {"x": {}}, {"model": {}}, {"weight_mode": {}}, {"formula": "a*x"}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.fit(**extra)

    def test_equation_uses_physical_column_labels(self):
        rows = [{"time": 0., "displacement": 1.}, {"time": 1., "displacement": 3.}]
        config = {"columns": [{"key": "time", "label": "$t$"}, {"key": "displacement", "label": "$x$"}],
                  "fit": {"x": "time", "y": "displacement"}}
        result = lab.make_fit(config["fit"], rows)
        tex = lab.tex_document(lab.validate_config(config, ["time", "displacement"]), rows, config, "fit", result)
        self.assertIn("$x$ $=a+b$ $t$", tex)

    def test_plain_command_label_is_safe_in_real_pdf(self):
        if os.environ.get("RUN_LATEX_TESTS") != "1":
            self.skipTest("Set RUN_LATEX_TESTS=1 for real compiler checks")
        rows = [{"x": 1., "y": 2.}]
        config = {"table_caption": r"50% & literal \input{marker.txt}",
                  "columns": [{"key": "x", "label": r"\input{marker.txt}"}, {"key": "y"}]}
        source = lab.tex_document(lab.validate_config(config, ["x", "y"]), rows, config, "table")
        path = self.root / "literal.tex"
        path.write_text(source, encoding="utf-8")
        lab.compile_pdf(path, lab.find_engine("xelatex"))
        self.assertGreater(path.with_suffix(".pdf").stat().st_size, 0)

    def test_style_ranges_and_panel_position_are_applied(self):
        fit = {"x": "x", "y": "y", "x_range": [-1, 5], "y_range": [0, 9], "curve_color": "#123ABC", "data_color": "blue", "marker": "diamond*", "result_position": "left"}
        result = lab.make_fit(fit, self.rows)
        tex = lab.tex_document(lab.validate_config({"fit": fit}, ["x", "y", "w"]), self.rows, {"fit": fit}, "fit", result)
        self.assertIn("xmin=-1,xmax=5", tex)
        self.assertIn("ymin=0,ymax=9", tex)
        self.assertIn("{HTML}{123ABC}", tex)
        self.assertLess(tex.index(r"\begin{tabular}"), tex.index(r"\begin{axis}"))
        self.assertLess(tex.index("no marks"), tex.index("only marks"))

    def test_log_axes_reject_nonpositive_data(self):
        fit = {"x": "x", "y": "y", "log_x": True}
        result = lab.make_fit(fit, self.rows)
        with self.assertRaisesRegex(ValueError, "positive"):
            lab.curve_samples(fit, result)

    @unittest.skipUnless(os.environ.get("RUN_LATEX_TESTS") == "1", "Set RUN_LATEX_TESTS=1 for real compiler checks")
    def test_real_compilation_of_small_values_and_theory(self):
        engine = lab.find_engine("xelatex")
        rows = [{"x": x, "y": 2 * x} for x in [1e-8, 2e-8, 3e-8]]
        for stage, model in [("table", "linear"), ("fit", "linear"), ("fit", "theory")]:
            fit = {"x": "x", "y": "y", "model": model}
            if model == "theory":
                fit.update(formula="k*x", fixed_parameters={"k": 2})
            result = lab.make_fit(fit, rows) if stage == "fit" else None
            source = lab.tex_document(lab.validate_config({"fit": fit}, ["x", "y"]), rows, {"fit": fit}, stage, result)
            path = self.root / f"{stage}_{model}.tex"
            path.write_text(source, encoding="utf-8")
            lab.compile_pdf(path, engine)
            pdf = path.with_suffix(".pdf")
            self.assertGreater(pdf.stat().st_size, 0)
            self.assertEqual(pdf.read_bytes()[:5], b"%PDF-")
            self.assertFalse(path.with_suffix(".log").exists())


if __name__ == "__main__":
    unittest.main()
