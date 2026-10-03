# Physics Lab Plotter

[中文文档](README.md)

`physics-lab-plotter` organizes user-supplied physics experiment images, text, CSV, spreadsheets or typed measurements into faithful tables, fitted curves and local PDFs.

## Capabilities and scope

- One data group, linear/nonlinear formula fitting, and theoretical curves with fixed constants.
- Relative weights, known absolute y standard deviations, parameter bounds and explicit fit status.
- Axis ranges, positive log axes, colors, markers, line widths, legends and a statistics panel outside the plot.
- Original decimal spelling is preserved by default. Nonfinite values, duplicate headers, malformed rows and unknown configuration fields are errors.
- Confirm uncertain image transcription; reuse confirmed data and proceed when a clear structured input already carries explicit fitting authorization.

The statistics panel reports parameters and standard errors, fixed constants, status, sample size, degrees of freedom, SSE, RMSE, residual standard error, Pearson r, weighted/unweighted R² and adjusted R² where defined. RMSE is `sqrt(SSE/n)`; residual standard error is `sqrt(SSE/(n-p))`.

Shared multi-group parameters, x-error fitting, error bars, confidence bands, residual panels and arbitrary multi-panel layouts require another suitable plotting tool; they are not bundled helper options.

## Installation and invocation

Install the complete repository under the name `physics-lab-plotter`, for example:

```text
git clone https://github.com/yuanmute/physics_experiment_drawer.git .agents/skills/physics-lab-plotter
```

See [platforms.md](references/platforms.md) for client directories and version caveats. Agent Skills compatibility is not a claim that all client releases have been tested.

```text
$physics-lab-plotter Build a table from these experiment images and flag unclear digits; do not fit yet.
$physics-lab-plotter The table is confirmed. Use t as horizontal and x as vertical, fit a line and generate a PDF.
```

## Local generator

Requires Python 3.10+ and XeLaTeX with ctex/Fandol, amsmath, amssymb, booktabs, longtable, TikZ and PGFPlots. The Python helper uses only the standard library.

Run the public synthetic example from the repository root:

```text
python scripts/make_lab_pdf.py --data examples/measurements.csv --config examples/plot.json --stage table --output-dir output
python scripts/make_lab_pdf.py --data examples/measurements.csv --config examples/plot.json --stage fit --output-dir output
```

For real work invoke the installed helper by its absolute path and keep inputs/outputs in the user's workspace. See [input-schema.md](references/input-schema.md). `--no-compile` creates TeX only; `--keep-build-files` preserves local diagnostic logs. Compilation failure preserves source and does not leave a stale same-name PDF presented as updated output.

## Privacy

The helper makes no network requests, scans no unrelated directories and reads no credentials. Ordinary display strings are escaped; mathematical labels use a restricted command vocabulary. Arbitrary TeX is unsupported. Generated source is compiled alone in a fresh temporary directory with shell escape disabled; temporary build artifacts are removed by default. A temporary directory is not an operating-system sandbox.

Chat/image-recognition services may process supplied material in the cloud according to the client's settings. Do not copy irrelevant names, student IDs or other identity details into outputs. Put private inputs in `data/` or `private/` and generated files in `output/`; these directories are Git-ignored. `examples/` contains synthetic public data only.

Contributors can use GitHub's private commit email. Changing future commit email does not remove existing history, caches, clones or forks. Keep credentials and personal material out of commits.

## Validation

```text
python -m unittest discover -s tests -v
```

With XeLaTeX installed, set `RUN_LATEX_TESTS=1` before running to check actual PDFs for scientific notation, fits and theory curves. In Windows PowerShell use `$env:RUN_LATEX_TESTS = '1'`.

The entry point is [SKILL.md](SKILL.md). Released under the [MIT License](LICENSE).
