---
name: physics-lab-plotter
description: Portable Agent Skills workflow for Codex, Claude Code, Cursor, WorkBuddy, and compatible clients. Convert physics-lab data from photos, screenshots, TXT, CSV, spreadsheets, or typed values into checked tables and Origin-style fitted curves. Use for transcription, unit-aware tables, confirmed linear or supplied-formula fits, graph refinement, and LaTeX PDF reports.
license: MIT
---

# Physics Lab Plotter

Create source-faithful experimental tables first, then fit only after the user confirms the transcription. Default to Chinese output and a LaTeX-compiled PDF unless the user requests another format.

## Cross-client portability

Treat this folder as a portable Agent Skills package. Keep `SKILL.md`, `references/`, and `scripts/` together when installing it. Place the folder at the client-specific skill directory described in [platforms.md](references/platforms.md); do not rewrite the core instructions for a particular model. `agents/openai.yaml` is optional Codex UI metadata and can be ignored by other clients.

## Workflow

1. Read every supplied source. For photos, transcribe only legible values; flag uncertain cells instead of guessing. Preserve measured values and distinguish calculated columns.
2. Draft a data-record table containing `n` plus every relevant quantity with its symbol/name, unit, and value. Add conversions or derived quantities only when their formula and inputs are known. Present the table to the user and explicitly request confirmation.
3. Do not begin fitting until the user confirms the table and names the horizontal variable, vertical variable, model, and any required physical formula or parameter constraints.
4. Create the fitting PDF with the bundled script. Use a black filled-square scatter series, a continuous contrasting fitted curve, complete axis labels with units, a concise legend, and a fit-results table beside the graph. Set axis limits and result-box position to avoid covering points.
5. Inspect the compiled PDF. If the user requests a revision, preserve confirmed values and modify only the requested fields: labels, units, decimals, range, colors, marker/line style, legend, result-table placement, formula, or layout. Recompile and inspect again.

## Default visual and statistical contract

- Make tables readable on A4: use a bordered long table for a single large record set, or compact `booktabs` tables for several short sets. Include a serial-number column even when the source does not provide one.
- Label axes as quantity and unit, for example `$T\,/\,\mathrm{K}$`; never infer a unit that is absent from the source.
- Use unweighted least squares unless the user gives measurement uncertainties or explicit weights. State the weighting in the result table.
- For a linear model report intercept and slope. For a supplied formula report every fitted parameter. Include each parameter's standard error when the fit has enough degrees of freedom.
- Put the following in the graph-side result table: model/equation, plotted dependent quantity, weighting, sample count, parameter estimates and standard errors, residual sum of squares, RMSE, Pearson correlation coefficient, $R^2$ (COD), and adjusted $R^2$. For a fixed-theory curve, replace fitted parameters with the given constants and report the experimental-versus-theory $R^2$.
- Do not silently change, omit, smooth, override, or fabricate data to improve a fit. Identify outliers or ambiguity for the user to decide.

## Create a PDF

Read [input-schema.md](references/input-schema.md) before preparing the CSV and JSON configuration. Then run:

```powershell
python scripts/make_lab_pdf.py --data measurements.csv --config plot.json --stage table --output-dir output
```

After the user confirms the table, run:

```powershell
python scripts/make_lab_pdf.py --data measurements.csv --config plot.json --stage fit --output-dir output
```

The script uses only the Python standard library and invokes `xelatex` by default. Use `--no-compile` only when the user requests TeX source without a PDF. For formula fits, provide safe math syntax such as `a*exp(-k*x)+c` and initial values in `parameters`; use the exact physical formula supplied by the user rather than substituting a more convenient one.

## Origin-equivalent refinement

Treat Origin as a visual reference, not a source of data. Prefer white background, legible ticks, restrained gridlines, distinct series styles, data points above curves, and a result panel that does not overlap data. For multiple groups, use one color/marker pair per group and state whether parameters are shared. Add residual plots, error bars, confidence bands, log axes, or multi-panel layouts only when they are supported by the data or requested by the user.
