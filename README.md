# Physics Lab Plotter

<p align="center"><a href="README.en.md">English documentation</a></p>

`physics-lab-plotter` 是一个遵循 Agent Skills 开放格式的物理实验数据记录与拟合绘图技能，可用于 Codex、Claude Code、Cursor、WorkBuddy 及其他兼容客户端。

## 能力

- 从实验数据照片、截图、TXT、CSV、表格或手工录入值中整理数据。
- 先生成带序号、物理量、单位和数值的记录表，等待用户确认后再拟合。
- 支持线性拟合和用户给定公式的非线性拟合。
- 生成散点、拟合曲线、图例和图旁统计小表。
- 默认使用 XeLaTeX 编译 PDF，并可按反馈修改坐标范围、标注、曲线和版式。

统计小表包含：方程、绘图量、权重、样本数、拟合参数及标准误差、残差平方和、RMSE、Pearson 相关系数、R²（COD）和调整后 R²。理论曲线还记录固定常量和实验—理论 R²。

## 跨平台安装

核心入口始终是同一个 `SKILL.md` 文件。将整个仓库目录放入对应客户端的技能目录，不要只复制脚本。

| 客户端 | 项目级目录 | 用户级目录 | 调用方式 |
| --- | --- | --- | --- |
| Codex | `.agents/skills/physics-lab-plotter/` | `~/.agents/skills/physics-lab-plotter/`；本机旧版也可使用 `~/.codex/skills/physics-lab-plotter/` | `$physics-lab-plotter` |
| Claude Code | `.claude/skills/physics-lab-plotter/` | `~/.claude/skills/physics-lab-plotter/` | `/physics-lab-plotter` |
| Cursor | `.cursor/skills/physics-lab-plotter/` | `~/.cursor/skills/physics-lab-plotter/` | Agent 自动选择或 `/physics-lab-plotter` |
| WorkBuddy | `.claude/skills/physics-lab-plotter/` | `~/.claude/skills/physics-lab-plotter/` | `/physics-lab-plotter` |

WorkBuddy 的技能入口沿用 Claude Code 目录；如果你的 WorkBuddy 版本提供了独立技能目录，仍应把同一仓库目录作为技能包安装。平台细节见 [references/platforms.md](references/platforms.md)。

## 调用示例

先要求记录表，不要立即拟合：

```text
$physics-lab-plotter 根据我上传的实验数据图片先生成记录表，暂时不要拟合。
```

表格确认后再指定变量和模型：

```text
$physics-lab-plotter 表格已确认。请用 t 拟合 x，模型为 y=a+b*x，并生成 PDF。
```

## 本地生成器

生成器只使用 Python 标准库；PDF 编译需要 `xelatex`。输入格式见 [references/input-schema.md](references/input-schema.md)。

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage table `
  --output-dir output
```

用户确认表格后运行：

```powershell
python scripts/make_lab_pdf.py `
  --data measurements.csv `
  --config plot.json `
  --stage fit `
  --output-dir output
```

只需要 TeX 源文件时增加 `--no-compile`。公式拟合支持 `+ - * / **`、括号和常用数学函数；所有拟合参数必须在 JSON 的 `parameters` 中提供初值。生成器不会静默删除、平滑、覆盖或捏造实验数据。

## 目录结构

```text
physics-lab-plotter/
├── SKILL.md
├── README.md                 # 中文入口
├── README.en.md              # English entry
├── LICENSE                   # MIT
├── agents/openai.yaml        # Codex UI metadata
├── references/
│   ├── input-schema.md
│   └── platforms.md
└── scripts/make_lab_pdf.py
```

## 参考格式

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Cursor Agent Skills](https://cursor.com/docs/context/skills)
- [WorkBuddy documentation](https://docs.work-buddy.ai/)

本项目采用 MIT License，详见 [LICENSE](LICENSE)。
