# Input schema

Inputs are a local UTF-8 CSV and UTF-8 JSON. CSV headers are distinct identifiers matching `[A-Za-z][A-Za-z0-9_]*`; surrounding spaces are trimmed. Every cell must be finite numeric data. Blank lines are ignored; missing/extra cells, duplicate headers, NaN and infinity are rejected with their location. A table can contain one row. Original decimal spelling is retained by default.

```csv
time,displacement,sigma
0.00,1.00,0.10
0.50,2.02,0.10
1.00,2.98,0.10
```

## Basic configuration

```json
{
  "table_caption": "实验数据记录表",
  "columns": [
    {"key": "time", "label": "$t$", "unit": "$\\mathrm{s}$"},
    {"key": "displacement", "label": "$x$", "unit": "$\\mathrm{cm}$"}
  ],
  "fit": {
    "x": "time",
    "y": "displacement",
    "model": "linear",
    "x_label": "$t\\,/\\,\\mathrm{s}$",
    "y_label": "$x\\,/\\,\\mathrm{cm}$",
    "title": "$x$ 与 $t$ 的线性拟合曲线",
    "legend_data": "实验数据",
    "legend_fit": "拟合曲线",
    "result_position": "right"
  }
}
```

Top-level fields are `table_caption`, `columns`, and `fit`. Unknown fields are errors. Omitted `columns` means all numeric CSV columns with literal header labels. Each column accepts `key`, `label`, `unit` and optional `precision` (integer 0–15); setting precision changes display rounding, not measurements or fitting. The table stage does not require `fit`.

## Display text and restricted math

Plain text is automatically escaped, including backslashes and TeX special characters. Put mathematical content inside paired `$...$`; use `\$` for a literal dollar. JSON requires backslashes to be doubled. Display fields are at most 2000 characters.

Math accepts letters, numbers, ordinary algebraic punctuation, balanced braces and a small allowlist: `\mathrm`, `\mathit`, `\mathbf`, `\mathsf`, `\mathtt`, `\mathcal`, `\mathbb`, `\text`, `\frac`, `\sqrt`, `\left`, `\right`, Greek symbols, arithmetic/comparison symbols, common math function names and accents. The complete allowlist is `MATH_COMMANDS` in the helper. Literal special characters need their supported escapes. File-reading commands, macro definitions, arbitrary TeX and `^^` character-code escapes are rejected. Plain text containing such a command is printed literally, never executed.

## Models and parameter constraints

`linear` fits `y=a+b*x` with an intercept. Use `formula` for floating and/or fixed parameters. `theory` evaluates a formula using only fixed constants; `formula` with no floating parameters also evaluates a theory curve.

```json
{
  "fit": {
    "x": "time",
    "y": "displacement",
    "model": "formula",
    "formula": "A*exp(-k*x)+c",
    "equation": "$y=A\\exp(-k x)+c$",
    "parameters": {"A": 2.0, "k": 0.2},
    "fixed_parameters": {"c": 1.0},
    "bounds": {"A": [0, null], "k": [0, null]},
    "domain": [0, 10],
    "max_iterations": 250,
    "tolerance": 1e-9
  }
}
```

`parameters` supplies finite initial values for floating parameters. `fixed_parameters` supplies finite constants used in both fitting and curve evaluation. Names must be identifiers and cannot overlap or shadow `x`, `pi`, or supported function names. Parameter bounds are `[lower, upper]`, with `null` for an open side; the initial value must lie within them. Theory curves cannot contain floating parameters. The helper rejects unidentifiable fits and iteration exhaustion.

Inside `formula`, the independent variable is always `x`. Allowed syntax is `+ - * / **` (or `^`), parentheses, numeric constants, named parameters, `pi`, and single-argument `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `exp`, `log`, `sqrt`, `abs`. No attributes, indexing, strings or arbitrary Python calls. `equation` is an optional display label, not the expression being evaluated.

Curve sampling stays between the minimum and maximum measured x. `domain` is an optional closed valid interval and must contain all measured x values. Axis padding never extends formula evaluation. A discontinuity inside the sampling interval raises an error rather than silently connecting invalid points.

## Weights and reported statistics

- Default: unweighted least squares; estimate parameter covariance with residual scale.
- `weight_key`: a positive finite CSV column of relative weights by default. Uniformly scaling these weights does not change estimates or standard errors.
- `sigma_key`: a positive finite CSV column of known absolute standard deviations of y; weights are `1/sigma²` and covariance has no additional estimated residual scale. x uncertainty is not modeled.
- `weight_mode`: `relative` or `absolute`. Use `absolute` with `weight_key` only if weights actually represent known inverse variances. `sigma_key` requires `absolute` and defaults to it.
- Set only one of `weight_key` and `sigma_key`.

The panel explicitly separates RMSE `sqrt(SSE/n)` from residual standard error `sqrt(SSE/(n-p))`, where p counts floating parameters. Weighted RMSE is `sqrt(sum(w*r²)/sum(w))`; weighted R² uses the weighted mean of y. Adjusted R² is the unweighted value with n-p residual degrees of freedom and is omitted for theory curves. Constant data or insufficient degrees of freedom produce `--` for undefined statistics.

## Plot configuration

| Field | Accepted values / meaning |
| --- | --- |
| `x_label`, `y_label`, `title`, `legend_data`, `legend_fit` | Escaped text with optional restricted math |
| `x_range`, `y_range` | Finite `[minimum, maximum]`, strictly increasing |
| `log_x`, `log_y` | Boolean; measurements, curve and explicit limits must be positive |
| `data_color`, `curve_color` | black, red, blue, gray, teal, orange, violet, magenta, green, cyan, brown, or `#RRGGBB` |
| `marker` | `square*`, `*`, `triangle*`, `diamond*`, `o`, `+`, `x` |
| `marker_size`, `line_width` | Points, positive and at most 10; defaults 1.7 and 1.2 |
| `legend_position` | north east, north west, south east, south west, outer north east |
| `result_position` | right (default), left, above, below; panel stays outside the plot |
| `max_iterations` | Integer 1–5000, default 250 |
| `tolerance` | Positive finite number at most 0.01, default 1e-9 |

The helper handles one group. Shared fits across groups, x-error fits, error bars, confidence bands, residual panels and arbitrary multi-panel layouts are not bundled features.

## Files and compilation

Run the helper using its installed absolute path and keep measurements/configuration in a user workspace. `--output-dir` selects output location; `--basename` accepts a simple ASCII filename (no separators). Outputs are `<basename>_<stage>.tex` and, after successful compilation, `.pdf`. `--no-compile` produces TeX only. An old same-name PDF is removed before compilation so failure cannot leave a stale result mistaken for the new one.

The default engine is `xelatex`; `--engine` can specify its absolute executable path. Required packages and Fandol fonts are checked by compilation. The helper compiles only its own generated markup in an empty temporary directory with `-no-shell-escape`, enforces a two-minute timeout per pass, verifies a nonempty PDF, and removes temporary build files. `--keep-build-files` preserves local diagnostic logs; do not publish them without inspecting their contents. The working directory is not a general TeX sandbox and arbitrary external TeX input is unsupported.
