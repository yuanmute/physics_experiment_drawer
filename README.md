# Physics Lab Plotter

[English documentation](README.en.md)

`physics-lab-plotter` 是物理实验数据记录与拟合绘图技能。它整理用户提供的照片、截图、TXT、CSV、表格或手工数据，保留测量值和单位，生成记录表、拟合曲线与本地 PDF。

## 能力与边界

- 支持单组线性拟合、给定公式的非线性拟合，以及包含固定常量的理论曲线。
- 支持相对权重、已知 y 测量标准差、参数上下界和明确的求解状态。
- 支持轴范围、对数轴、颜色、标记、线宽、图例，以及位于图外的统计表。
- 原始小数写法默认保留；非有限值、重复表头、缺失数据和未知配置会报错。
- 图片转录不明确时先确认；已经确认的数据或明确授权拟合的清晰 CSV 不重复等待确认。

统计表包含参数与标准误差、固定常量、求解状态、样本数、自由度、SSE、RMSE、残差标准误、Pearson r、加权与未加权 R²，以及适用时的调整后 R²。RMSE 与残差标准误的定义分别是 `sqrt(SSE/n)` 与 `sqrt(SSE/(n-p))`。

多组共享参数、x 误差拟合、误差棒、置信带、残差面板和任意多面板布局需要其他合适绘图工具；本地生成器没有这些配置入口。

## 安装与调用

将完整仓库安装为 `physics-lab-plotter` 文件夹，例如：

```text
git clone https://github.com/yuanmute/physics_experiment_drawer.git .agents/skills/physics-lab-plotter
```

其他客户端目录与版本注意事项见 [platforms.md](references/platforms.md)。支持 Agent Skills 不代表所有客户端版本已测试。

```text
$physics-lab-plotter 根据实验图片先生成记录表，标出不清楚的数字，暂时不要拟合。
$physics-lab-plotter 表格已确认。以 t 为横轴、x 为纵轴，做线性拟合并生成 PDF。
```

## 本地运行

需要 Python 3.10+ 和 XeLaTeX，后者需包含 ctex/Fandol、amsmath、amssymb、booktabs、longtable、TikZ 与 PGFPlots。Python 代码仅使用标准库。

在仓库根目录运行公开的合成示例：

```text
python scripts/make_lab_pdf.py --data examples/measurements.csv --config examples/plot.json --stage table --output-dir output
python scripts/make_lab_pdf.py --data examples/measurements.csv --config examples/plot.json --stage fit --output-dir output
```

实际使用时，通过技能安装目录的绝对路径调用脚本，把输入与输出留在用户工作区。CSV/JSON 协议见 [input-schema.md](references/input-schema.md)。`--no-compile` 只生成 TeX；`--keep-build-files` 保留本地诊断日志。编译失败会保留源码，并避免旧 PDF 被误当成新结果。

## 隐私

生成器没有网络请求，不扫描其他目录或读取凭证。普通文字自动转义，数学标注只接受受限命令；不接受任意 TeX。生成的源码在新建临时目录编译，并关闭 shell escape，临时编译文件默认清理。临时目录本身不是操作系统沙箱。

聊天客户端或图片识别服务可能处理云端数据，这由所用客户端的设置决定。不要把不相关的姓名、学号或身份信息带入成果。私人输入放入 `data/` 或 `private/`，生成文件放入 `output/`；这些目录已被 Git 忽略。`examples/` 仅包含合成公开数据。

提交者可使用 GitHub 的隐私邮箱。更换后续提交邮箱不会自动清除旧历史、缓存、已有克隆或 fork；不要把凭证或个人材料放进提交。

## 验证

```text
python -m unittest discover -s tests -v
```

安装 XeLaTeX 后，设置环境变量 `RUN_LATEX_TESTS=1` 再运行，检查科学计数法、拟合与理论曲线的实际 PDF 输出。Windows PowerShell 可先执行 `$env:RUN_LATEX_TESTS = '1'`。

核心入口为 [SKILL.md](SKILL.md)；采用 [MIT License](LICENSE)。
