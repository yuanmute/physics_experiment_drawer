#!/usr/bin/env python3
"""Create checked physics-lab tables and Origin-style fit PDFs from CSV + JSON."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


SAFE_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "exp": math.exp, "log": math.log, "sqrt": math.sqrt, "abs": abs,
}
SAFE_NAMES = {"pi": math.pi, **SAFE_FUNCS}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, float]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV must contain a header row.")
        keys = [key.strip() for key in reader.fieldnames]
        rows: list[dict[str, float]] = []
        for number, raw in enumerate(reader, 2):
            if not any((value or "").strip() for value in raw.values()):
                continue
            try:
                rows.append({key: float((raw[key] or "").strip()) for key in keys})
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Row {number} contains a missing or non-numeric value.") from exc
    if len(rows) < 2:
        raise ValueError("At least two numeric rows are required.")
    return keys, rows


def safe_expression(expression: str, parameter_names: list[str]):
    expression = expression.replace("^", "**")
    tree = ast.parse(expression, mode="eval")
    allowed_names = {"x", *parameter_names, *SAFE_NAMES}
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
        ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub,
        ast.UAdd,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Unsupported formula element: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"Unsupported formula name: {node.id}")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS):
            raise ValueError("Only named standard math functions are allowed in a formula.")
    return compile(tree, "<formula>", "eval")


def evaluate_formula(code, x: float, names: list[str], values: list[float]) -> float:
    namespace = {"x": x, **SAFE_NAMES, **dict(zip(names, values))}
    try:
        value = float(eval(code, {"__builtins__": {}}, namespace))
    except (ArithmeticError, ValueError, OverflowError) as exc:
        raise ValueError("Formula is undefined for one or more supplied values.") from exc
    if not math.isfinite(value):
        raise ValueError("Formula produced a non-finite value.")
    return value


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    aug = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(aug[row][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise ValueError("Fit parameters are not independently identifiable.")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        divisor = aug[col][col]
        aug[col] = [value / divisor for value in aug[col]]
        for row in range(size):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [a - factor * b for a, b in zip(aug[row], aug[col])]
    return [row[-1] for row in aug]


def inverse(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    return [solve(matrix, [1.0 if row == col else 0.0 for row in range(size)]) for col in range(size)]


def residuals(code, xs, ys, names, values):
    predicted = [evaluate_formula(code, x, names, values) for x in xs]
    return predicted, [y - fitted for y, fitted in zip(ys, predicted)]


def nonlinear_fit(code, xs, ys, names, initial, weights):
    values = initial[:]
    count, parameter_count = len(xs), len(names)
    damping = 1e-3
    for _ in range(250):
        predicted, residual = residuals(code, xs, ys, names, values)
        cost = sum(weight * item * item for weight, item in zip(weights, residual))
        jacobian: list[list[float]] = []
        for x, base in zip(xs, predicted):
            row = []
            for index, value in enumerate(values):
                step = 1e-6 * max(1.0, abs(value))
                upper, lower = values[:], values[:]
                upper[index] += step
                lower[index] -= step
                derivative = (evaluate_formula(code, x, names, upper) - evaluate_formula(code, x, names, lower)) / (2 * step)
                row.append(derivative)
            jacobian.append(row)
        normal = [[0.0] * parameter_count for _ in range(parameter_count)]
        right = [0.0] * parameter_count
        for row, residual_item, weight in zip(jacobian, residual, weights):
            for i in range(parameter_count):
                right[i] += weight * row[i] * residual_item
                for j in range(parameter_count):
                    normal[i][j] += weight * row[i] * row[j]
        trial_normal = [row[:] for row in normal]
        for i in range(parameter_count):
            trial_normal[i][i] += damping * max(normal[i][i], 1.0)
        try:
            step = solve(trial_normal, right)
            candidate = [value + change for value, change in zip(values, step)]
            _, candidate_residual = residuals(code, xs, ys, names, candidate)
            candidate_cost = sum(weight * item * item for weight, item in zip(weights, candidate_residual))
        except ValueError:
            damping *= 10
            continue
        if candidate_cost < cost:
            values = candidate
            damping = max(damping / 3, 1e-12)
            if max(abs(change) for change in step) < 1e-10:
                break
        else:
            damping *= 10
    predicted, residual = residuals(code, xs, ys, names, values)
    # Rebuild J'WJ at the accepted result for parameter standard errors.
    normal = [[0.0] * parameter_count for _ in range(parameter_count)]
    for x, weight in zip(xs, weights):
        row = []
        for index, value in enumerate(values):
            step = 1e-6 * max(1.0, abs(value))
            upper, lower = values[:], values[:]
            upper[index] += step
            lower[index] -= step
            row.append((evaluate_formula(code, x, names, upper) - evaluate_formula(code, x, names, lower)) / (2 * step))
        for i in range(parameter_count):
            for j in range(parameter_count):
                normal[i][j] += weight * row[i] * row[j]
    sse = sum(item * item for item in residual)
    dof = count - parameter_count
    if dof > 0:
        try:
            covariance = inverse(normal)
            scale = sse / dof
            errors = [math.sqrt(max(0.0, covariance[i][i] * scale)) for i in range(parameter_count)]
        except ValueError:
            errors = [math.nan] * parameter_count
    else:
        errors = [math.nan] * parameter_count
    return values, errors, predicted, residual


def linear_fit(xs, ys, weights):
    total_weight = sum(weights)
    mean_x = sum(weight * x for weight, x in zip(weights, xs)) / total_weight
    mean_y = sum(weight * y for weight, y in zip(weights, ys)) / total_weight
    sxx = sum(weight * (x - mean_x) ** 2 for weight, x in zip(weights, xs))
    if sxx <= 0:
        raise ValueError("The x values must not all be equal.")
    slope = sum(weight * (x - mean_x) * (y - mean_y) for weight, x, y in zip(weights, xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    predicted = [intercept + slope * x for x in xs]
    residual = [y - fitted for y, fitted in zip(ys, predicted)]
    dof = len(xs) - 2
    sse = sum(item * item for item in residual)
    if dof > 0:
        variance = sse / dof
        errors = [math.sqrt(variance * (1 / total_weight + mean_x * mean_x / sxx)), math.sqrt(variance / sxx)]
    else:
        errors = [math.nan, math.nan]
    return [intercept, slope], errors, predicted, residual


def correlation(xs, ys):
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return numerator / denominator if denominator else math.nan


def make_fit(fit, rows):
    x_key, y_key = fit["x"], fit["y"]
    if any(x_key not in row or y_key not in row for row in rows):
        raise ValueError("fit.x and fit.y must be CSV headers.")
    xs, ys = [row[x_key] for row in rows], [row[y_key] for row in rows]
    weight_key = fit.get("weight_key")
    if weight_key:
        try:
            weights = [row[weight_key] for row in rows]
        except KeyError as exc:
            raise ValueError("weight_key must be a CSV header.") from exc
        if any(weight <= 0 for weight in weights):
            raise ValueError("All supplied weights must be positive.")
        weight_label = f"相对权重：{weight_key}"
    else:
        weights, weight_label = [1.0] * len(rows), "不加权"
    model = fit.get("model", "linear")
    if model == "linear":
        names, values, errors, predicted, residual = ["a", "b"], *linear_fit(xs, ys, weights)
        equation = fit.get("equation", "$y=a+b x$")
    elif model == "formula":
        parameters = fit.get("parameters")
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("Formula fitting requires a non-empty fit.parameters object.")
        names = list(parameters)
        code = safe_expression(str(fit.get("formula", "")), names)
        values, errors, predicted, residual = nonlinear_fit(code, xs, ys, names, [float(parameters[name]) for name in names], weights)
        equation = fit.get("equation", f"$y={fit['formula']}$")
    else:
        raise ValueError("fit.model must be 'linear' or 'formula'.")
    sse = sum(value * value for value in residual)
    n, p = len(xs), len(values)
    total = sum((value - sum(ys) / n) ** 2 for value in ys)
    r2 = 1 - sse / total if total else math.nan
    adjusted = 1 - (1 - r2) * (n - 1) / (n - p) if n > p and math.isfinite(r2) else math.nan
    return {
        "xs": xs, "ys": ys, "predicted": predicted, "names": names, "values": values, "errors": errors,
        "equation": equation, "weight_label": weight_label, "n": n, "sse": sse,
        "rmse": math.sqrt(sse / (n - p)) if n > p else math.nan,
        "r": correlation(xs, ys), "r2": r2, "adjusted_r2": adjusted,
        "fixed": fit.get("fixed_parameters", {}),
    }


def sci(value: float, digits: int = 6) -> str:
    if not math.isfinite(value):
        return "--"
    text = f"{value:.{digits}g}"
    if "e" not in text:
        return text
    coefficient, exponent = text.split("e")
    return f"{coefficient}\\times 10^{{{int(exponent)}}}"


def tex_document(columns, rows, config, stage, result=None):
    caption = config.get("table_caption", "表 1：实验数据记录表")
    headers = ["$n$"] + [f"{column.get('label', column['key'])} / {column.get('unit', '')}" for column in columns]
    table_rows = []
    for number, row in enumerate(rows, 1):
        values = [str(number)]
        for column in columns:
            precision = column.get("precision")
            value = row[column["key"]]
            values.append(f"{value:.{precision}f}" if isinstance(precision, int) else sci(value))
        table_rows.append(" & ".join(values) + r" \\")
    spec = "|" + "|".join("r" for _ in headers) + "|"
    tex = [
        r"\documentclass[UTF8,a4paper]{ctexart}", r"\usepackage[margin=1.35cm]{geometry}",
        r"\usepackage{booktabs,longtable,pgfplots,tikz,caption}", r"\pgfplotsset{compat=1.18}",
        r"\setlength{\tabcolsep}{4pt}", r"\renewcommand{\arraystretch}{1.22}", r"\pagestyle{empty}", r"\begin{document}",
        r"\small", f"\\begin{{longtable}}{{{spec}}}", f"\\caption{{{caption}}}\\\\", r"\hline",
        " & ".join(headers) + r" \\", r"\hline", r"\endfirsthead", r"\hline",
        " & ".join(headers) + r" \\", r"\hline", r"\endhead",
    ]
    for row in table_rows:
        tex.extend([row, r"\hline"])
    tex.extend([r"\end{longtable}"])
    if stage == "table":
        tex.extend([r"\end{document}"])
        return "\n".join(tex)
    fit = config["fit"]
    xmin, xmax = min(result["xs"]), max(result["xs"])
    padding = (xmax - xmin) * 0.07 or 1
    sorted_pairs = sorted(zip(result["xs"], result["predicted"]))
    curve_x = [xmin - padding + (xmax - xmin + 2 * padding) * index / 250 for index in range(251)]
    if fit.get("model", "linear") == "linear":
        curve_y = [result["values"][0] + result["values"][1] * x for x in curve_x]
    else:
        code = safe_expression(str(fit["formula"]), result["names"])
        curve_y = [evaluate_formula(code, x, result["names"], result["values"]) for x in curve_x]
    points = " ".join(f"({sci(x)},{sci(y)})" for x, y in zip(result["xs"], result["ys"]))
    curve = " ".join(f"({sci(x)},{sci(y)})" for x, y in zip(curve_x, curve_y))
    stats = [
        ("方程", result["equation"]), ("绘图", fit.get("y_label", fit["y"])), ("权重", result["weight_label"]), ("样本数", str(result["n"])),
    ]
    for name, value, error in zip(result["names"], result["values"], result["errors"]):
        stats.extend([(f"参数 ${name}$", f"${sci(value)}$"), ("", f"$\\pm {sci(error)}$")])
    for name, value in result["fixed"].items():
        stats.append((f"固定 ${name}$", f"${sci(float(value))}$"))
    stats.extend([
        ("残差平方和", f"${sci(result['sse'])}$"), ("RMSE", f"${sci(result['rmse'])}$"),
        ("Pearson's r", f"${sci(result['r'])}$"), ("$R^2$ (COD)", f"${sci(result['r2'])}$"),
        ("调整后 $R^2$", f"${sci(result['adjusted_r2'])}$"),
    ])
    stat_rows = "\n".join(f"{name} & {value} \\\\" for name, value in stats)
    tex.extend([
        r"\clearpage", r"\begin{minipage}[t]{0.72\textwidth}", r"\vspace{0pt}\centering", r"\begin{tikzpicture}",
        r"\begin{axis}[width=\linewidth,height=0.62\linewidth,axis lines=box,grid=major,grid style={gray!20},",
        f"xlabel={{{fit.get('x_label', fit['x'])}}},ylabel={{{fit.get('y_label', fit['y'])}}},",
        f"title={{{fit.get('title', '拟合曲线')}}},legend pos={fit.get('legend_position', 'south east')},",
        f"xmin={sci(xmin-padding)},xmax={sci(xmax+padding)},tick align=outside]",
        f"\\addplot+[only marks,mark=square*,mark options={{fill=black}},black] coordinates {{{points}}};",
        f"\\addlegendentry{{{fit.get('legend_data', '实验数据')}}}",
        f"\\addplot+[no marks,ultra thick,red] coordinates {{{curve}}};",
        f"\\addlegendentry{{{fit.get('legend_fit', '拟合曲线')}}}", r"\end{axis}", r"\end{tikzpicture}", r"\end{minipage}\hfill",
        r"\begin{minipage}[t]{0.25\textwidth}", r"\vspace{0pt}\scriptsize\centering",
        r"\begin{tabular}{@{}l l@{}}\toprule", stat_rows, r"\bottomrule\end{tabular}", r"\end{minipage}",
        r"\end{document}",
    ])
    return "\n".join(tex)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage", choices=("table", "fit"), required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--basename", default="physics_lab")
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--engine", default="xelatex")
    args = parser.parse_args()
    try:
        keys, rows = read_csv(args.data)
        config = json.loads(args.config.read_text(encoding="utf-8"))
        columns = config.get("columns") or [{"key": key, "label": key, "unit": ""} for key in keys]
        if any(column.get("key") not in keys for column in columns):
            raise ValueError("Every configured column key must be present in the CSV.")
        result = make_fit(config["fit"], rows) if args.stage == "fit" else None
        args.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = args.output_dir / f"{args.basename}_{args.stage}.tex"
        tex_path.write_text(tex_document(columns, rows, config, args.stage, result), encoding="utf-8")
        print(f"Wrote {tex_path}")
        if args.no_compile:
            return
        engine = shutil.which(args.engine)
        if not engine:
            raise RuntimeError(f"LaTeX engine '{args.engine}' was not found. Re-run with --no-compile or install it.")
        for _ in range(2):
            completed = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=args.output_dir, text=True, capture_output=True)
            if completed.returncode:
                print(completed.stdout[-4000:], file=sys.stderr)
                print(completed.stderr[-2000:], file=sys.stderr)
                raise RuntimeError(f"LaTeX compilation failed; inspect {tex_path.with_suffix('.log')}")
        print(f"Wrote {tex_path.with_suffix('.pdf')}")
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
