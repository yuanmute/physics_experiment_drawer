#!/usr/bin/env python3
"""Create checked physics-lab tables and fitted PDFs from local CSV + JSON."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SAFE_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "exp": math.exp, "log": math.log, "sqrt": math.sqrt, "abs": abs,
}
SAFE_NAMES = {"pi": math.pi, **SAFE_FUNCS}
KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
TEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
# Formatting and mathematical symbols only; no file access or macro creation.
MATH_COMMANDS = set("""
mathrm mathit mathbf mathsf mathtt mathcal mathbb text frac sqrt
left right cdot times div pm mp le ge neq approx sim propto infty
sin cos tan arcsin arccos arctan exp log ln min max
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota
kappa lambda mu nu xi pi rho sigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
sum prod int partial nabla circ hat bar vec dot ddot overline
""".split())
MATH_ESCAPES = set(",;! {}_%#$")
COLORS = {"black", "red", "blue", "gray", "teal", "orange", "violet", "magenta", "green", "cyan", "brown"}
MARKERS = {"square*", "*", "triangle*", "diamond*", "o", "+", "x"}
LEGEND_POSITIONS = {"north east", "north west", "south east", "south west", "outer north east"}
FIT_FIELDS = {
    "x", "y", "model", "formula", "equation", "parameters", "fixed_parameters",
    "weight_key", "sigma_key", "weight_mode", "bounds", "max_iterations", "tolerance",
    "x_label", "y_label", "title", "legend_data", "legend_fit", "legend_position",
    "result_position", "x_range", "y_range", "domain", "log_x", "log_y",
    "data_color", "curve_color", "marker", "marker_size", "line_width",
}


class MeasurementRow(dict):
    """Numeric values plus original decimal spellings for faithful tables."""
    def __init__(self, values, source_text):
        super().__init__(values)
        self.source_text = source_text


def finite_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a finite number.")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number.")
    return number


def check_fields(value, allowed, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown {field} fields: {', '.join(sorted(unknown))}.")


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        try:
            keys = [key.strip() for key in next(reader)]
        except StopIteration as exc:
            raise ValueError("CSV must contain a header row.") from exc
        if not keys or any(not KEY.fullmatch(key) for key in keys):
            raise ValueError("CSV headers must start with an ASCII letter and contain only letters, digits or underscores; use labels for display text.")
        if len(set(keys)) != len(keys):
            raise ValueError("CSV headers must be unique after trimming whitespace.")
        rows = []
        for raw in reader:
            if not any(value.strip() for value in raw):
                continue
            if len(raw) != len(keys):
                raise ValueError(f"Row {reader.line_num} must contain exactly {len(keys)} cells.")
            text = dict(zip(keys, (value.strip() for value in raw)))
            values = {key: finite_number(text[key], f"Row {reader.line_num}, column {key}") for key in keys}
            rows.append(MeasurementRow(values, text))
    if not rows:
        raise ValueError("At least one numeric row is required.")
    return keys, rows


def plain_tex(text):
    return "".join(TEX_ESCAPES.get(char, char) for char in text)


def math_tex(text):
    if "^^" in text:
        raise ValueError("TeX character-code escapes are not allowed in mathematical labels.")
    depth, index = 0, 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            command = re.match(r"\\([A-Za-z]+|.)", text[index:])
            if not command or command[1] not in MATH_COMMANDS | MATH_ESCAPES:
                raise ValueError("Mathematical labels allow only documented formatting commands and symbols.")
            index += len(command[0])
            continue
        if not (char.isalnum() or char in " +-=*/().,:;|<>[]{}_^!'\t"):
            raise ValueError("Unsupported character in a mathematical label.")
        depth += (char == "{") - (char == "}")
        if depth < 0:
            raise ValueError("Unbalanced braces in a mathematical label.")
        index += 1
    if depth:
        raise ValueError("Unbalanced braces in a mathematical label.")
    return text


def display_tex(value):
    """Escape plain text and allow a bounded math-markup vocabulary."""
    if not isinstance(value, str) or len(value) > 2000:
        raise ValueError("Display fields must be strings of at most 2000 characters.")
    if any(ord(char) < 32 and char not in "\t\n" for char in value):
        raise ValueError("Control characters are not allowed in display fields.")
    value = value.replace(r"\$", "\uFFF0")
    pieces = value.split("$")
    if len(pieces) % 2 == 0:
        raise ValueError("Mathematical labels need paired $ delimiters; use \\$ for a literal dollar.")
    return "".join("$" + math_tex(part) + "$" if index % 2 else plain_tex(part.replace("\uFFF0", "$"))
                   for index, part in enumerate(pieces))


def interval(value, field):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field} must be [minimum, maximum].")
    result = [finite_number(item, field) for item in value]
    if result[0] >= result[1]:
        raise ValueError(f"{field} minimum must be less than maximum.")
    return result


def parameters_object(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    if any(not KEY.fullmatch(name) or name in {"x", *SAFE_NAMES} for name in value):
        raise ValueError(f"{field} names must be identifiers and must not shadow x, pi or math functions.")
    return {name: finite_number(number, f"{field}.{name}") for name, number in value.items()}


def parameter_bounds(fit, names, initial):
    result = []
    for name, value in zip(names, initial):
        bounds = fit.get("bounds", {}).get(name, [None, None])
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError(f"bounds.{name} must be [lower, upper], using null for an unbounded side.")
        low = -math.inf if bounds[0] is None else finite_number(bounds[0], f"bounds.{name}")
        high = math.inf if bounds[1] is None else finite_number(bounds[1], f"bounds.{name}")
        if low >= high or not low <= value <= high:
            raise ValueError(f"Initial value for {name} must lie within distinct parameter bounds.")
        result.append((low, high))
    return result


def validate_fit(fit, keys):
    check_fields(fit, FIT_FIELDS, "fit")
    if any(not isinstance(fit.get(name), str) or fit[name] not in keys for name in ("x", "y")):
        raise ValueError("fit.x and fit.y must be CSV headers.")
    model = fit.get("model", "linear")
    if not isinstance(model, str) or model not in {"linear", "formula", "theory"}:
        raise ValueError("fit.model must be linear, formula or theory.")
    floating = parameters_object(fit.get("parameters", {}), "fit.parameters")
    fixed = parameters_object(fit.get("fixed_parameters", {}), "fit.fixed_parameters")
    if floating.keys() & fixed.keys():
        raise ValueError("Floating and fixed parameters must have different names.")
    if model == "linear" and any(field in fit for field in ("formula", "parameters", "fixed_parameters", "bounds")):
        raise ValueError("Use model=formula for fixed or bounded parameters.")
    if model == "theory" and floating:
        raise ValueError("Theory curves cannot have floating parameters.")
    if model != "linear":
        safe_expression(fit.get("formula", ""), [*floating, *fixed])
    if fit.get("weight_key") and fit.get("sigma_key"):
        raise ValueError("Set only one of weight_key or sigma_key.")
    for name in ("weight_key", "sigma_key"):
        if fit.get(name) is not None and (not isinstance(fit[name], str) or fit[name] not in keys):
            raise ValueError(f"fit.{name} must be a CSV header or null.")
    weight_mode = fit.get("weight_mode", "absolute" if fit.get("sigma_key") else "relative")
    if not isinstance(weight_mode, str) or weight_mode not in {"relative", "absolute"}:
        raise ValueError("weight_mode must be relative or absolute.")
    if fit.get("sigma_key") and fit.get("weight_mode", "absolute") != "absolute":
        raise ValueError("sigma_key describes absolute y standard deviations; use weight_mode=absolute.")
    if fit.get("weight_mode") == "absolute" and not (fit.get("sigma_key") or fit.get("weight_key")):
        raise ValueError("Absolute weights require weight_key or sigma_key.")
    for field in ("x_label", "y_label", "title", "legend_data", "legend_fit", "equation"):
        if field in fit:
            display_tex(fit[field])
    for field in ("x_range", "y_range", "domain"):
        if field in fit:
            fit[field] = interval(fit[field], f"fit.{field}")
    for field in ("log_x", "log_y"):
        if field in fit and type(fit[field]) is not bool:
            raise ValueError(f"fit.{field} must be true or false.")
    for field in ("data_color", "curve_color"):
        if field in fit:
            color = fit[field]
            if not isinstance(color, str) or (color not in COLORS and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color)):
                raise ValueError(f"fit.{field} must be a supported color name or #RRGGBB.")
    for field, default, allowed in (("marker", "square*", MARKERS), ("legend_position", "south east", LEGEND_POSITIONS),
                                     ("result_position", "right", {"right", "left", "above", "below"})):
        if not isinstance(fit.get(field, default), str) or fit.get(field, default) not in allowed:
            raise ValueError(f"Unsupported {field}; allowed values: {', '.join(sorted(allowed))}.")
    for field, default, upper in (("marker_size", 1.7, 10), ("line_width", 1.2, 10), ("tolerance", 1e-9, 0.01)):
        number = finite_number(fit.get(field, default), f"fit.{field}")
        if not 0 < number <= upper:
            raise ValueError(f"fit.{field} must be positive and at most {upper}.")
        if field in fit:
            fit[field] = number
    iterations = fit.get("max_iterations", 250)
    if type(iterations) is not int or not 1 <= iterations <= 5000:
        raise ValueError("max_iterations must be an integer from 1 to 5000.")
    check_fields(fit.get("bounds", {}), set(floating), "bounds")
    parameter_bounds(fit, list(floating), list(floating.values()))


def validate_config(config, keys):
    check_fields(config, {"table_caption", "columns", "fit"}, "configuration")
    display_tex(config.get("table_caption", "实验数据记录表"))
    columns = config.get("columns")
    if columns is None:
        columns = [{"key": key, "label": key, "unit": ""} for key in keys]
    if not isinstance(columns, list) or not columns:
        raise ValueError("columns must be a non-empty list.")
    used = set()
    for column in columns:
        check_fields(column, {"key", "label", "unit", "precision"}, "column")
        if not isinstance(column.get("key"), str) or column["key"] not in keys or column["key"] in used:
            raise ValueError("Configured column keys must be distinct CSV headers.")
        used.add(column["key"])
        display_tex(column.get("label", column["key"]))
        display_tex(column.get("unit", ""))
        precision = column.get("precision")
        if precision is not None and (type(precision) is not int or not 0 <= precision <= 15):
            raise ValueError("column.precision must be an integer from 0 to 15.")
    if "fit" in config:
        validate_fit(config["fit"], keys)
    return columns


def safe_expression(expression, parameter_names):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 1000:
        raise ValueError("formula must be a non-empty expression of at most 1000 characters.")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Invalid mathematical formula syntax.") from exc
    allowed_names = {"x", *parameter_names, *SAFE_NAMES}
    allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
                     ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)
    nodes = list(ast.walk(tree))
    if len(nodes) > 250:
        raise ValueError("Formula is too complex.")
    for node in nodes:
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Unsupported formula element: {type(node).__name__}.")
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float):
                raise ValueError("Formula constants must be finite numbers.")
            finite_number(node.value, "Formula constant")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"Unsupported formula name: {node.id}.")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS or len(node.args) != 1 or node.keywords):
            raise ValueError("Use only single-argument standard math functions.")
    return compile(tree, "<formula>", "eval")


def evaluate_formula(code, x, names, values, fixed=None):
    namespace = {"x": x, **SAFE_NAMES, **(fixed or {}), **dict(zip(names, values))}
    try:
        value = float(eval(code, {"__builtins__": {}}, namespace))
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise ValueError("Formula is undefined for one or more supplied values.") from exc
    if not math.isfinite(value):
        raise ValueError("Formula produced a non-finite value.")
    return value


def solve(matrix, vector):
    size = len(vector)
    aug = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    scales = [max(map(abs, row)) for row in matrix]
    if any(scale == 0 or not math.isfinite(scale) for scale in scales):
        raise ValueError("Fit parameters are not independently identifiable.")
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(aug[row][col]) / scales[row])
        if abs(aug[pivot][col]) <= 1e-12 * scales[pivot]:
            raise ValueError("Fit parameters are not independently identifiable.")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scales[col], scales[pivot] = scales[pivot], scales[col]
        divisor = aug[col][col]
        aug[col] = [value / divisor for value in aug[col]]
        for row in range(size):
            if row != col:
                factor = aug[row][col]
                aug[row] = [a - factor * b for a, b in zip(aug[row], aug[col])]
    result = [row[-1] for row in aug]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("Numerically unstable fit; rescale variables or parameters.")
    return result


def inverse(matrix):
    columns = [solve(matrix, [float(row == col) for row in range(len(matrix))]) for col in range(len(matrix))]
    return [list(row) for row in zip(*columns)]


def normalized_weights(weights):
    if not weights or any(not math.isfinite(value) or value <= 0 for value in weights):
        raise ValueError("All weights must be finite and positive.")
    scale = max(weights)
    normalized = [value / scale for value in weights]
    if any(value == 0 for value in normalized):
        raise ValueError("Weight range is too large; rescale measurement uncertainties.")
    return normalized, scale


def linear_fit(xs, ys, weights, absolute=False):
    weights, scale = normalized_weights(weights)
    total_weight = sum(weights)
    mean_x = sum(weight * x for weight, x in zip(weights, xs)) / total_weight
    mean_y = sum(weight * y for weight, y in zip(weights, ys)) / total_weight
    sxx = sum(weight * (x - mean_x) ** 2 for weight, x in zip(weights, xs))
    if sxx <= 0 or not math.isfinite(sxx):
        raise ValueError("x values must vary and have a numerically usable range.")
    slope = sum(weight * (x - mean_x) * (y - mean_y) for weight, x, y in zip(weights, xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    predicted = [intercept + slope * x for x in xs]
    residual = [y - fitted for y, fitted in zip(ys, predicted)]
    dof = len(xs) - 2
    if absolute or dof > 0:
        variance = 1 / scale if absolute else sum(weight * item ** 2 for weight, item in zip(weights, residual)) / dof
        errors = [math.sqrt(variance * (1 / total_weight + mean_x ** 2 / sxx)), math.sqrt(variance / sxx)]
    else:
        errors = [math.nan, math.nan]
    return [intercept, slope], errors, predicted, residual


def residuals(code, xs, ys, names, values, fixed):
    predicted = [evaluate_formula(code, x, names, values, fixed) for x in xs]
    return predicted, [y - fitted for y, fitted in zip(ys, predicted)]


def normal_equations(code, xs, names, values, fixed, bounds, weights, residual):
    p = len(names)
    normal, right = [[0.0] * p for _ in range(p)], [0.0] * p
    for x, weight, item in zip(xs, weights, residual):
        base = evaluate_formula(code, x, names, values, fixed)
        row = []
        for index, value in enumerate(values):
            delta = 1e-6 * max(abs(value), 1.0)
            trials = []
            for candidate in (min(value + delta, bounds[index][1]), max(value - delta, bounds[index][0])):
                if candidate == value:
                    continue
                varied = values[:]
                varied[index] = candidate
                try:
                    trials.append((candidate, evaluate_formula(code, x, names, varied, fixed)))
                except ValueError:
                    pass
            if not trials:
                raise ValueError("Cannot evaluate parameter derivatives; revise initial values or bounds.")
            if len(trials) == 2:
                derivative = (trials[0][1] - trials[1][1]) / (trials[0][0] - trials[1][0])
            else:
                derivative = (trials[0][1] - base) / (trials[0][0] - value)
            row.append(derivative)
        for i in range(p):
            right[i] += weight * row[i] * item
            for j in range(p):
                normal[i][j] += weight * row[i] * row[j]
    return normal, right


def nonlinear_fit(code, xs, ys, names, initial, weights, fixed=None, bounds=None,
                  absolute=False, max_iterations=250, tolerance=1e-9):
    fixed = fixed or {}
    bounds = bounds or [(-math.inf, math.inf)] * len(names)
    weights, scale = normalized_weights(weights)
    values, damping, reason = initial[:], 1e-3, None
    for iteration in range(1, max_iterations + 1):
        predicted, residual = residuals(code, xs, ys, names, values, fixed)
        cost = sum(weight * item ** 2 for weight, item in zip(weights, residual))
        normal, right = normal_equations(code, xs, names, values, fixed, bounds, weights, residual)
        if not math.isfinite(cost):
            raise ValueError("Fit cost is non-finite; rescale the data.")
        # A zero gradient is not convergence when the parameters are unidentifiable.
        inverse(normal)
        projected = [0.0 if (values[i] == bounds[i][0] and item < 0) or
                          (values[i] == bounds[i][1] and item > 0) else item
                     for i, item in enumerate(right)]
        gradient = max(abs(item) / math.sqrt(normal[i][i]) for i, item in enumerate(projected))
        if cost == 0 or gradient <= tolerance * max(1.0, math.sqrt(cost)):
            reason = "residual or projected gradient tolerance"
            break
        trial_normal = [row[:] for row in normal]
        for i in range(len(names)):
            trial_normal[i][i] += damping * normal[i][i]
        step = solve(trial_normal, right)
        candidate = [max(low, min(high, value + change)) for value, change, (low, high) in zip(values, step, bounds)]
        try:
            _, candidate_residual = residuals(code, xs, ys, names, candidate, fixed)
            candidate_cost = sum(weight * item ** 2 for weight, item in zip(weights, candidate_residual))
        except ValueError:
            candidate_cost = math.inf
        if candidate_cost < cost:
            improvement = cost - candidate_cost
            change = max(abs(new - old) / max(1.0, abs(old)) for new, old in zip(candidate, values))
            values = candidate
            damping = max(damping / 3, 1e-12)
            if change <= tolerance or improvement <= tolerance * max(1.0, cost):
                reason = "parameter or objective tolerance"
                break
        else:
            damping *= 10
            if damping > 1e16:
                raise ValueError("Fit stalled without convergence; revise initial values, scaling or bounds.")
    if reason is None:
        raise ValueError(f"Fit did not converge in {max_iterations} iterations; revise the model or initial values.")
    predicted, residual = residuals(code, xs, ys, names, values, fixed)
    normal, _ = normal_equations(code, xs, names, values, fixed, bounds, weights, residual)
    covariance = inverse(normal)
    dof = len(xs) - len(names)
    if absolute or dof > 0:
        variance = 1 / scale if absolute else sum(weight * item ** 2 for weight, item in zip(weights, residual)) / dof
        errors = [math.sqrt(max(0.0, covariance[i][i] * variance)) for i in range(len(names))]
    else:
        errors = [math.nan] * len(names)
    return values, errors, predicted, residual, {"status": "converged", "iterations": iteration, "reason": reason}


def correlation(xs, ys):
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return numerator / denominator if denominator else math.nan


def make_fit(fit, rows):
    if not rows:
        raise ValueError("Fit requires data.")
    validate_fit(fit, set(rows[0]))
    xs = [finite_number(row[fit["x"]], "x measurement") for row in rows]
    ys = [finite_number(row[fit["y"]], "y measurement") for row in rows]
    if "domain" in fit and any(not fit["domain"][0] <= x <= fit["domain"][1] for x in xs):
        raise ValueError("Every measured x must lie within the declared formula domain.")
    sigma_key, weight_key = fit.get("sigma_key"), fit.get("weight_key")
    absolute = fit.get("weight_mode", "absolute" if sigma_key else "relative") == "absolute"
    if sigma_key:
        sigmas = [finite_number(row[sigma_key], "y standard deviation") for row in rows]
        if any(value <= 0 for value in sigmas):
            raise ValueError("All y standard deviations must be positive.")
        weights = [1 / value ** 2 for value in sigmas]
        weight_label = f"绝对误差：{sigma_key}"
    elif weight_key:
        weights = [finite_number(row[weight_key], "weight") for row in rows]
        weight_label = f"{'绝对' if absolute else '相对'}权重：{weight_key}"
    else:
        weights, weight_label = [1.0] * len(rows), "不加权"
    norm_weights, _ = normalized_weights(weights)
    model = fit.get("model", "linear")
    fixed = parameters_object(fit.get("fixed_parameters", {}), "fixed_parameters")
    if model == "linear":
        if len(rows) < 2:
            raise ValueError("Linear fitting requires at least two data rows.")
        names = ["a", "b"]
        values, errors, predicted, residual = linear_fit(xs, ys, weights, absolute)
        equation = fit.get("equation", f"{fit['y']} = a + b * {fit['x']}")
        status = {"status": "converged", "iterations": 1, "reason": "analytic linear solution"}
    else:
        parameters = parameters_object(fit.get("parameters", {}), "parameters")
        names = list(parameters)
        code = safe_expression(fit["formula"], [*names, *fixed])
        equation = fit.get("equation", fit["y"] + " = " + re.sub(r"\bx\b", fit["x"], fit["formula"]))
        if model == "theory" or not names:
            values, errors = [], []
            predicted, residual = residuals(code, xs, ys, [], [], fixed)
            status = {"status": "theory", "iterations": 0, "reason": "fixed formula evaluation"}
        else:
            if len(rows) < len(names):
                raise ValueError("Fitting requires at least as many data rows as floating parameters.")
            bounds = parameter_bounds(fit, names, list(parameters.values()))
            values, errors, predicted, residual, status = nonlinear_fit(
                code, xs, ys, names, list(parameters.values()), weights, fixed, bounds,
                absolute, fit.get("max_iterations", 250), fit.get("tolerance", 1e-9))
    if any(not math.isfinite(value) for value in [*values, *predicted, *residual]):
        raise ValueError("Fit produced a non-finite result.")
    sse = sum(value ** 2 for value in residual)
    n, p = len(xs), len(values)
    total = sum((value - sum(ys) / n) ** 2 for value in ys)
    r2 = 1 - sse / total if total else math.nan
    weighted_mean = sum(weight * y for weight, y in zip(norm_weights, ys)) / sum(norm_weights)
    weighted_total = sum(weight * (y - weighted_mean) ** 2 for weight, y in zip(norm_weights, ys))
    weighted_sse = sum(weight * item ** 2 for weight, item in zip(norm_weights, residual))
    warnings = []
    if n <= p and not absolute:
        warnings.append("自由度不足，无法估计参数标准误差")
    if fit.get("bounds") and any(value == limit for name, value in zip(names, values) for limit in fit["bounds"].get(name, []) if limit is not None):
        warnings.append("参数位于边界，标准误差仅为局部线性近似")
    return {
        "xs": xs, "ys": ys, "predicted": predicted, "residual": residual,
        "names": names, "values": values, "errors": errors, "fixed": fixed,
        "equation": equation, "weight_label": weight_label, "n": n, "p": p,
        "sse": sse, "rmse": math.sqrt(sse / n),
        "residual_standard_error": math.sqrt(sse / (n - p)) if n > p else math.nan,
        "weighted_rmse": math.sqrt(weighted_sse / sum(norm_weights)),
        "weighted_r2": 1 - weighted_sse / weighted_total if weighted_total else math.nan,
        "r": correlation(xs, ys), "r2": r2,
        "adjusted_r2": 1 - (1 - r2) * (n - 1) / (n - p) if p and n > p and math.isfinite(r2) else math.nan,
        "fit_status": status, "warnings": warnings,
    }


def sci(value, digits=6):
    if not math.isfinite(value):
        return "--"
    text = f"{value:.{digits}g}"
    if "e" not in text:
        return text
    coefficient, exponent = text.split("e")
    return f"{coefficient}\\times 10^{{{int(exponent)}}}"


def coordinate(value):
    if not math.isfinite(value):
        raise ValueError("Plot coordinates must be finite.")
    return f"{value:.16g}"


def curve_samples(fit, result):
    # Axis padding is visual only; never extend formula evaluation into it.
    low, high = min(result["xs"]), max(result["xs"])
    if "domain" in fit:
        low, high = max(low, fit["domain"][0]), min(high, fit["domain"][1])
    if fit.get("log_x") and low <= 0:
        raise ValueError("Logarithmic x axes require positive measurements.")
    if low == high:
        xs = [low]
    elif fit.get("log_x"):
        xs = [math.exp(math.log(low) + (math.log(high) - math.log(low)) * i / 250) for i in range(251)]
    else:
        xs = [low + (high - low) * i / 250 for i in range(251)]
    if fit.get("model", "linear") == "linear":
        ys = [result["values"][0] + result["values"][1] * x for x in xs]
    else:
        code = safe_expression(fit["formula"], [*result["names"], *result["fixed"]])
        try:
            ys = [evaluate_formula(code, x, result["names"], result["values"], result["fixed"]) for x in xs]
        except ValueError as exc:
            raise ValueError("Formula is undefined inside the plotting interval; specify a valid continuous model domain.") from exc
    if fit.get("log_y") and any(y <= 0 for y in [*ys, *result["ys"]]):
        raise ValueError("Logarithmic y axes require positive measurements and curve values.")
    return xs, ys


def color_definition(name, value):
    if value.startswith("#"):
        return f"\\definecolor{{{name}}}{{HTML}}{{{value[1:]}}}"
    return f"\\colorlet{{{name}}}{{{value}}}"


def tex_document(columns, rows, config, stage, result=None):
    validate_config(config, list(rows[0]))
    headers = ["$n$"]
    for column in columns:
        label = display_tex(column.get("label", column["key"]))
        unit = display_tex(column.get("unit", ""))
        headers.append(label + (" / " + unit if unit else ""))
    table_rows = []
    for number, row in enumerate(rows, 1):
        values = [str(number)]
        for column in columns:
            value = finite_number(row[column["key"]], "table value")
            precision = column.get("precision")
            if precision is not None:
                values.append(f"{value:.{precision}f}")
            else:
                original = getattr(row, "source_text", {}).get(column["key"], str(value))
                values.append(plain_tex(original))
        table_rows.append(" & ".join(values) + r" \\")
    tex = [
        r"\documentclass[UTF8,a4paper,fontset=fandol]{ctexart}",
        r"\usepackage[margin=1.35cm]{geometry}",
        r"\usepackage{amsmath,amssymb,booktabs,longtable,pgfplots,tikz,caption}",
        r"\pgfplotsset{compat=1.18}", r"\setlength{\tabcolsep}{4pt}",
        r"\renewcommand{\arraystretch}{1.22}", r"\pagestyle{empty}", r"\begin{document}",
        r"\small", r"\begin{longtable}{|" + "|".join("r" for _ in headers) + "|}",
        "\\caption{" + display_tex(config.get("table_caption", "实验数据记录表")) + r"}\\",
        r"\hline", " & ".join(headers) + r" \\", r"\hline", r"\endfirsthead",
        r"\hline", " & ".join(headers) + r" \\", r"\hline", r"\endhead",
    ]
    for row in table_rows:
        tex.extend([row, r"\hline"])
    tex.append(r"\end{longtable}")
    if stage == "table":
        return "\n".join([*tex, r"\end{document}"])
    fit = config["fit"]
    curve_x, curve_y = curve_samples(fit, result)
    xmin, xmax = min(result["xs"]), max(result["xs"])
    padding = (xmax - xmin) * 0.07 or max(abs(xmin) * 0.07, 1.0)
    x_range = fit.get("x_range", [xmin / 1.1, xmax * 1.1] if fit.get("log_x") else [xmin - padding, xmax + padding])
    if fit.get("log_x") and x_range[0] <= 0:
        raise ValueError("A logarithmic x_range must be positive.")
    if fit.get("log_y") and "y_range" in fit and fit["y_range"][0] <= 0:
        raise ValueError("A logarithmic y_range must be positive.")
    points = " ".join(f"({coordinate(x)},{coordinate(y)})" for x, y in zip(result["xs"], result["ys"]))
    curve = " ".join(f"({coordinate(x)},{coordinate(y)})" for x, y in zip(curve_x, curve_y))
    status_label = "理论曲线" if result["fit_status"]["status"] == "theory" else "已收敛"
    equation_tex = display_tex(result["equation"])
    if fit.get("model", "linear") == "linear" and "equation" not in fit:
        label_map = {column["key"]: display_tex(column.get("label", column["key"])) for column in columns}
        equation_tex = label_map.get(fit["y"], display_tex(fit["y"])) + " $=a+b$ " + label_map.get(fit["x"], display_tex(fit["x"]))
    stats = [
        ("方程", equation_tex), ("绘图", display_tex(fit.get("y_label", fit["y"]))),
        ("权重", plain_tex(result["weight_label"])), ("状态", status_label),
        ("样本数", str(result["n"])), ("自由度", str(result["n"] - result["p"])),
    ]
    for name, value, error in zip(result["names"], result["values"], result["errors"]):
        stats.append(("参数 " + plain_tex(name), f"${sci(value)} \\pm {sci(error)}$"))
    for name, value in result["fixed"].items():
        stats.append(("固定 " + plain_tex(name), f"${sci(value)}$"))
    for label, key in (("残差平方和", "sse"), ("RMSE", "rmse"), ("残差标准误", "residual_standard_error"),
                       ("加权 RMSE", "weighted_rmse"), ("Pearson's r", "r"), ("未加权 $R^2$", "r2"),
                       ("加权 $R^2$", "weighted_r2"), ("调整后 $R^2$", "adjusted_r2")):
        stats.append((label, f"${sci(result[key])}$"))
    stat_rows = "\n".join(name + " & " + value + r" \\" for name, value in stats)
    options = [
        r"width=\linewidth,height=0.65\linewidth,axis lines=box,grid=major,grid style={gray!20}",
        "xlabel={" + display_tex(fit.get("x_label", fit["x"])) + "}",
        "ylabel={" + display_tex(fit.get("y_label", fit["y"])) + "}",
        "title={" + display_tex(fit.get("title", "拟合曲线")) + "}",
        "legend pos=" + fit.get("legend_position", "south east"),
        f"xmin={coordinate(x_range[0])},xmax={coordinate(x_range[1])},tick align=outside",
    ]
    if "y_range" in fit:
        options.append(f"ymin={coordinate(fit['y_range'][0])},ymax={coordinate(fit['y_range'][1])}")
    if fit.get("log_x"):
        options.append("xmode=log")
    if fit.get("log_y"):
        options.append("ymode=log")
    position = fit.get("result_position", "right")
    chart_width, panel_width = ("0.67", "0.30") if position in {"left", "right"} else ("0.88", "0.88")
    chart = [
        f"\\begin{{minipage}}[t]{{{chart_width}\\textwidth}}", r"\vspace{0pt}\centering",
        r"\begin{tikzpicture}", "\\begin{axis}[" + ",\n".join(options) + "]",
        f"\\addplot+[no marks,color=labcurve,line width={coordinate(fit.get('line_width', 1.2))}pt] coordinates {{{curve}}};",
        "\\addlegendentry{" + display_tex(fit.get("legend_fit", "理论曲线" if status_label == "理论曲线" else "拟合曲线")) + "}",
        f"\\addplot+[only marks,mark={fit.get('marker', 'square*')},mark size={coordinate(fit.get('marker_size', 1.7))}pt,color=labdata,mark options={{fill=labdata}}] coordinates {{{points}}};",
        "\\addlegendentry{" + display_tex(fit.get("legend_data", "实验数据")) + "}",
        r"\end{axis}", r"\end{tikzpicture}", r"\end{minipage}",
    ]
    panel = [
        f"\\begin{{minipage}}[t]{{{panel_width}\\textwidth}}", r"\vspace{0pt}\scriptsize",
        r"\begin{tabular}{@{}p{0.43\linewidth} p{0.50\linewidth}@{}}\toprule",
        stat_rows, r"\bottomrule\end{tabular}",
    ]
    panel.extend(plain_tex(warning) + r"\par" for warning in result["warnings"])
    panel.append(r"\end{minipage}")
    tex.extend([r"\par\medskip", color_definition("labcurve", fit.get("curve_color", "red")),
                color_definition("labdata", fit.get("data_color", "black"))])
    if position == "right":
        tex.extend([*chart, r"\hfill", *panel])
    elif position == "left":
        tex.extend([*panel, r"\hfill", *chart])
    elif position == "above":
        tex.extend([*panel, r"\par\medskip", *chart])
    else:
        tex.extend([*chart, r"\par\medskip", *panel])
    return "\n".join([*tex, r"\end{document}"])


def find_engine(requested):
    path = Path(requested)
    if path.name.lower() not in {"xelatex", "xelatex.exe"}:
        raise ValueError("Only XeLaTeX is supported; --engine may specify its absolute executable path.")
    if path.is_absolute():
        if not path.is_file():
            raise RuntimeError("The specified XeLaTeX executable was not found.")
        return str(path)
    if str(path) != path.name:
        raise ValueError("Use xelatex from PATH or an absolute executable path.")
    # Do not implicitly search the working directory on Windows.
    for entry in os.get_exec_path():
        if not entry:
            continue
        folder = Path(entry).resolve()
        if folder == Path.cwd():
            continue
        candidate = folder / ("xelatex.exe" if os.name == "nt" else "xelatex")
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError("XeLaTeX was not found. Source is preserved; use --no-compile or provide --engine.")


def compile_pdf(tex_path, engine, keep_build_files=False):
    """Compile generated markup alone in a fresh directory, with shell escape off."""
    with tempfile.TemporaryDirectory(prefix="physics-lab-") as temporary:
        build = Path(temporary)
        shutil.copyfile(tex_path, build / "document.tex")
        for _ in range(2):
            try:
                completed = subprocess.run(
                    [engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "document.tex"],
                    cwd=build, capture_output=True, timeout=120)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("LaTeX compilation timed out; TeX source is preserved.") from exc
            if completed.returncode:
                log = build / "document.log"
                if keep_build_files and log.exists():
                    shutil.copyfile(log, tex_path.with_suffix(".log"))
                raise RuntimeError("LaTeX compilation failed; source is preserved. Use --keep-build-files for a local diagnostic log.")
        pdf = build / "document.pdf"
        if not pdf.is_file() or pdf.stat().st_size == 0:
            raise RuntimeError("LaTeX did not produce a non-empty PDF; source is preserved.")
        shutil.copyfile(pdf, tex_path.with_suffix(".pdf"))
        if keep_build_files:
            for suffix in (".log", ".aux", ".out"):
                source = build / ("document" + suffix)
                if source.exists():
                    shutil.copyfile(source, tex_path.with_suffix(suffix))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage", choices=("table", "fit"), required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--basename", default="physics_lab")
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--keep-build-files", action="store_true")
    parser.add_argument("--engine", default="xelatex")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.basename):
            raise ValueError("basename must be a simple ASCII filename without path separators.")
        keys, rows = read_csv(args.data)
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        columns = validate_config(config, keys)
        if args.stage == "fit" and "fit" not in config:
            raise ValueError("The fit stage requires a fit configuration.")
        result = make_fit(config["fit"], rows) if args.stage == "fit" else None
        source = tex_document(columns, rows, config, args.stage, result)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = args.output_dir / f"{args.basename}_{args.stage}.tex"
        tex_path.write_text(source, encoding="utf-8")
        print(f"Wrote {tex_path}")
        if args.no_compile:
            return
        tex_path.with_suffix(".pdf").unlink(missing_ok=True)
        compile_pdf(tex_path, find_engine(args.engine), args.keep_build_files)
        print(f"Wrote {tex_path.with_suffix('.pdf')}")
    except (OSError, ValueError, KeyError, RuntimeError, ArithmeticError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
