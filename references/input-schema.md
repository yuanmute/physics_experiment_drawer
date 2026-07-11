# Input schema for `make_lab_pdf.py`

Keep CSV data in UTF-8. The first row contains machine-safe column keys; values must be numeric. The script creates the serial-number column itself.

```csv
time,displacement
0.00,0.02
0.50,0.81
```

Use this JSON shape. Display strings are LaTeX-ready, so enclose mathematical labels in `$...$` and write units with `\mathrm{...}` when needed.

```json
{
  "table_caption": "表 1：实验数据记录表",
  "columns": [
    {"key": "time", "label": "$t$", "unit": "$\\mathrm{s}$", "precision": 2},
    {"key": "displacement", "label": "$x$", "unit": "$\\mathrm{cm}$", "precision": 3}
  ],
  "fit": {
    "x": "time",
    "y": "displacement",
    "x_label": "$t\\,/\\,\\mathrm{s}$",
    "y_label": "$x\\,/\\,\\mathrm{cm}$",
    "title": "$x$ 与 $t$ 的线性拟合曲线",
    "model": "linear",
    "legend_data": "实验数据",
    "legend_fit": "拟合曲线",
    "result_position": "north west"
  }
}
```

For a supplied formula, set `model` to `formula`, use `x` as the independent-variable name inside `formula`, and provide every floating parameter with a reasonable initial value. Use only `+ - * / **`, parentheses, numbers, parameter names, and `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `exp`, `log`, `sqrt`, `abs`, or `pi`.

```json
{
  "fit": {
    "x": "frequency",
    "y": "amplitude",
    "model": "formula",
    "formula": "A/sqrt((1-(x/x0)**2)**2+(zeta*x/x0)**2)",
    "equation": "$y=A/\\sqrt{[1-(x/x_0)^2]^2+(\\zeta x/x_0)^2}$",
    "parameters": {"A": 1.0, "x0": 1.0, "zeta": 0.05},
    "weight_key": null
  }
}
```

Set `weight_key` to a positive numeric CSV column only when the user supplies weights. Treat it as a relative least-squares weight. Fixed theoretical constants can be placed in `fixed_parameters`; they appear in the result panel and are not fitted.
