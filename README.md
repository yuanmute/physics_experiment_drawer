# Physics Lab Plotter

物理实验数据记录与拟合绘图技能 / Physics experiment data tables and fitting plots for Codex.

## 中文说明

`physics-lab-plotter` 面向物理实验报告中的数据整理和拟合绘图。它可以处理用户提供的实验数据照片、截图、TXT、CSV、表格或手工录入数据，生成可核对的数据记录表，并在用户确认数据后进行拟合与绘图。

技能遵循以下顺序：

1. 转录数据并生成记录表，包含序号、物理量名称/符号、单位、原始值和明确可计算的换算量。
2. 把记录表交给用户核对；在用户确认前不进行拟合。
3. 对用户指定的两个变量进行线性拟合或给定公式的非线性拟合。
4. 生成 Origin 风格的散点图、拟合曲线、图例和图旁统计小表。
5. 默认用 XeLaTeX 编译 PDF，并根据用户反馈重新调整坐标范围、标注、曲线、颜色、图例和版式。

统计小表包括：方程、绘图量、权重、样本数、拟合参数及标准误差、残差平方和、RMSE、Pearson 相关系数、R²（COD）和调整后 R²。理论曲线则记录固定常量以及实验值与理论值的 R²。

### 目录结构

```text
physics-lab-plotter/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── references/input-schema.md
└── scripts/make_lab_pdf.py
```

### 使用方式

在 Codex 中调用：

```text
$physics-lab-plotter 根据我上传的实验数据图片先生成记录表，暂时不要拟合。
```

确认表格后，再指定横轴量、纵轴量和模型：

```text
$physics-lab-plotter 表格已确认。请用 t 拟合 x，模型为 y=a+b*x，并生成 PDF。
```

### 本地生成器

生成器只使用 Python 标准库；PDF 编译需要安装 `xelatex`。先按 [references/input-schema.md](references/input-schema.md) 准备 UTF-8 CSV 和 JSON 配置，然后运行：

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage table `
  --output-dir output
```

用户确认数据后运行拟合阶段：

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage fit `
  --output-dir output
```

只需要 TeX 源文件时，可增加 `--no-compile`。公式拟合支持 `+ - * / **`、括号和常用数学函数；所有参数必须在 JSON 的 `parameters` 中提供初值。不要为了改善拟合而删除、平滑、覆盖或捏造实验数据。

## English documentation

`physics-lab-plotter` is a Codex skill for organizing physics-lab measurements and producing publication-ready fitting plots. It accepts photographs, screenshots, TXT, CSV, spreadsheets, or typed values.

The workflow is deliberately staged:

1. Transcribe the measurements and build a numbered table with quantity names/symbols, units, raw values, and only justified derived quantities.
2. Show the table for user confirmation. No fit is run before confirmation.
3. Fit the two user-selected variables with ordinary linear least squares or a supplied nonlinear formula.
4. Draw Origin-style scatter points, a fitted curve, a legend, and a compact results panel beside the graph.
5. Compile a PDF with XeLaTeX by default and regenerate it when the user requests visual or mathematical changes.

The results panel reports the equation, plotted dependent quantity, weighting, sample count, parameter estimates and standard errors, residual sum of squares, RMSE, Pearson correlation, R² (COD), and adjusted R². Theory-only curves report their fixed constants and experimental-versus-theory R².

### Repository layout

```text
physics-lab-plotter/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── references/input-schema.md
└── scripts/make_lab_pdf.py
```

### Invocation

Use the skill in Codex with:

```text
$physics-lab-plotter Build a data-record table from my uploaded experiment image; do not fit until I confirm it.
```

After confirmation, specify the x variable, y variable, and model:

```text
$physics-lab-plotter The table is confirmed. Fit x against t with y=a+b*x and produce the PDF.
```

### Command-line generator

The generator uses only the Python standard library. PDF compilation requires `xelatex`. Prepare a UTF-8 CSV and JSON configuration according to [references/input-schema.md](references/input-schema.md), then run:

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage table `
  --output-dir output
```

After the table has been confirmed:

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage fit `
  --output-dir output
```

Use `--no-compile` when only the TeX source is wanted. Formula fitting accepts `+ - * / **`, parentheses, and common math functions; every fitted parameter must have an initial value in JSON `parameters`. The generator never silently drops, smooths, overrides, or fabricates measurements.

## License and contribution

No license is declared by this repository. Add a license before redistributing it. Improvements should preserve the confirmation gate, source-faithful data handling, and reproducible LaTeX output.
