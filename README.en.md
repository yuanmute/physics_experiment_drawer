# Physics Lab Plotter

<p align="center"><a href="README.md">中文文档</a></p>

`physics-lab-plotter` is an Agent Skills-compatible workflow for physics experiment data tables and fitting plots. It can be used with Codex, Claude Code, Cursor, WorkBuddy, and other clients that support the open `SKILL.md` format.

## Capabilities

- Organize measurements from experiment photos, screenshots, TXT, CSV, spreadsheets, or typed values.
- Build a numbered, unit-aware record table and wait for user confirmation before fitting.
- Fit two selected variables with ordinary linear least squares or a supplied nonlinear formula.
- Draw scatter points, fitted curves, legends, and a compact statistics panel beside the graph.
- Compile a PDF with XeLaTeX by default and revise ranges, labels, curves, and layout on request.

The statistics panel reports the equation, plotted quantity, weighting, sample count, parameter estimates and standard errors, residual sum of squares, RMSE, Pearson correlation, R² (COD), and adjusted R². Theory curves also report fixed constants and experimental-versus-theory R².

## Cross-client installation

The canonical entry point is the same `SKILL.md` file everywhere. Put the entire repository directory into the client’s skill directory; do not copy only the script.

| Client | Project directory | User directory | Invocation |
| --- | --- | --- | --- |
| Codex | `.agents/skills/physics-lab-plotter/` | `~/.agents/skills/physics-lab-plotter/`; the legacy local path `~/.codex/skills/physics-lab-plotter/` also works in this setup | `$physics-lab-plotter` |
| Claude Code | `.claude/skills/physics-lab-plotter/` | `~/.claude/skills/physics-lab-plotter/` | `/physics-lab-plotter` |
| Cursor | `.cursor/skills/physics-lab-plotter/` | `~/.cursor/skills/physics-lab-plotter/` | Automatic selection or `/physics-lab-plotter` |
| WorkBuddy | `.claude/skills/physics-lab-plotter/` | `~/.claude/skills/physics-lab-plotter/` | `/physics-lab-plotter` |

WorkBuddy uses the Claude Code skill entry point. If your WorkBuddy release exposes a separate skill directory, install this same repository directory there; the root `SKILL.md` remains the portable contract. See [references/platforms.md](references/platforms.md) for details.

## Invocation examples

First request a record table and explicitly defer fitting:

```text
$physics-lab-plotter Build a record table from my uploaded experiment image; do not fit yet.
```

After confirming the table, specify the variables and model:

```text
$physics-lab-plotter The table is confirmed. Fit x against t with y=a+b*x and produce the PDF.
```

## Local generator

The generator uses only the Python standard library. PDF compilation requires `xelatex`. See [references/input-schema.md](references/input-schema.md) for the CSV and JSON schema.

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage table `
  --output-dir output
```

After the user confirms the table:

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage fit `
  --output-dir output
```

Use `--no-compile` when only the TeX source is needed. Formula fitting accepts `+ - * / **`, parentheses, and common math functions; every fitted parameter must have an initial value in JSON `parameters`. The generator never silently drops, smooths, overrides, or fabricates measurements.

## Repository layout

```text
physics-lab-plotter/
├── SKILL.md
├── README.md                 # Chinese entry
├── README.en.md              # English entry
├── LICENSE                   # MIT
├── agents/openai.yaml        # Codex UI metadata
├── references/
│   ├── input-schema.md
│   └── platforms.md
└── scripts/make_lab_pdf.py
```

## Format references

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Cursor Agent Skills](https://cursor.com/docs/context/skills)
- [WorkBuddy documentation](https://docs.work-buddy.ai/)

This project is released under the MIT License; see [LICENSE](LICENSE).
