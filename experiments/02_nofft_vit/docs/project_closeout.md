# ACX720-V3 阶段结束与换板交接

结束日期：2026-11-25。用户决定在教学板上做到当前阶段，未来换用性能更好的板卡再继续。
**本阶段已结束，不再安排本板上的新增模型实现。完整模型部署未完成。**
机器可读状态见 [closeout.json](../reports/closeout.json)。

## 留下了哪些成果

完成模型/数据审查、FP32 基线、7 组 PTQ 比较、W16A16_M125 导出验证、
48 位整数累加与重定标、串口协议、GELU 查表以及两层串联。
ACX720-V3 上的 DDR 全容量独立测试已由用户观察确认通过。
最后的 `head.4 → GELU → head.7` 在真实板上执行 1,000 组开发样本隐藏向量，
42,000 个最终记录与软件整数参考逐项相同，见 [最终实板报告](../reports/integer_tail_validation.md)。

最终 bit 为 `build/integer_tail_hw/acx720_v3_integer_tail.bit`，SHA-256：

```text
84a5e5fef733823ea5dca9ccd8006bc472c123f4be51da17c8017947f9cce41b
```

上板范围：192→96 全连接、GELU、96→42 全连接。前面的模型在电脑上执行。
中间值不经过电脑，但串口只返回最后一层记录；中间值另由 RTL 仿真比较。
在本次开发样本上最终输出记录完全一致，不等于对所有输入的形式化证明。

## 明确未完成的部分

- 其余卷积/全连接、注意力、LayerNorm、Softmax 等完整计算图的整数硬件实现。
- 推理与 DDR 权重/激活读写的集成；DDR 测试和当前推理是两个独立工程。
- 完整输入图像到最终系数的端到端实板验收、整体速度和功耗优化。
- 8,700 组预留集的最终推理验收。已检查文件完整性，但未用于推理或选参。
- 真实采集数据的完整预处理规范、系数物理单位及应用可接受误差，仍待后续项目确认。

当前实现占满 50 个 BRAM Tile，这是完整查表和当前存储映射的结果，不表示模型一定无法在该芯片上运行。
本次结束原因是用户选择保留教学成果并以后换板，而非已经证明某个部署方案不可行。

## GitHub 中保存什么

提交 RTL、板级适配、仿真、Python/Tcl、依赖清单、教程和小型 JSON/文本报告。
原始模型源码包和权重、样本、厂家资料、软件安装包、Python 环境、bit 及本地复现包都不提交。
原始资料继续留在 `F:/no-fft`，厂家资料留在被忽略的 `board/vendor/`。
原始资料/厂商文件没有被删除或搬动。本仓库的归档不等于这些外部资料也已备份到 GitHub。

`reports/` 保留按阶段生成的历史证据，包括早期 `pending` / `not_yet_tested`。
不把旧报告改写成最终验收结果；最终结论看本页、结束记录和最新实板验收报告。
文件哈希记录当时的字节；Git 换行转换、工具版本、路径和重建时间可能改变哈希，不能据此承诺重建 bit 字节一致。
已有报告中的本地盘符、源路径和串口号是历史上下文，迁移时使用实际路径与设备。

## 恢复本次分段验证

本地复现包：`artifacts/acx720_v3_closeout_20261125.zip`，约 4 MiB，默认不上传。
包含五个已生成 bit、整数末层/两层段的 MEM 和参考 NPZ、主要构建报告、数据划分清单与 FP32 开发参考。
不包含原始模型包、10,000 个样本、完整量化导出、厂家 MIG 包、Python/Vivado/Icarus 环境；
它是分段恢复包，不是完整模型训练或整网重建备份。包的逐文件清单位于
`experiments/02_nofft_vit/build/closeout_bundle_manifest.json`（包内）。

请把这个包另存到自己的备份位置；它当前仍在同一块本地磁盘上，尚不是异地备份。
GitHub 只保存代码与记录，丢失本地包和原始资料后无法只靠 Git 恢复未公开的权重与数据。

在新的仓库副本根目录准备 Python 3.11 和 Icarus Verilog（`iverilog`、`vvp` 位于 PATH），
把本地包复制到对应 `artifacts/` 后执行：

```powershell
Expand-Archive -LiteralPath experiments\02_nofft_vit\artifacts\acx720_v3_closeout_20261125.zip -DestinationPath .
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r experiments\02_nofft_vit\requirements-host.txt
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_tail.py
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_tail_uart.py
```

仅在空的恢复副本中解压，避免覆盖现有结果。仿真会写该副本的报告；历史原件留在 Git 中。
恢复包已按这个目录布局在独立副本中做过解压与两层/串口仿真检查，见 [归档检查](../reports/archive_preflight.json)。
需要重新生成 bit 时用 [两层教程](integer_tail.md) 的 Vivado 命令；需要上板时再人工下载，并运行
`software/check_integer_tail_board.py --port 实际端口 --limit 1000`。
复现旧硬件是可选恢复动作，不是本阶段待完成任务。

在原工作目录重新打包，可运行 `scripts/package_closeout.py --output 新的本地zip路径`。
脚本先检查已验收产物哈希，再打包并逐文件验证；已存在的包不会被覆盖。
打包脚本默认目录被 Git 忽略，指定其他位置时也不要把含权重/向量的包加入 Git。

## 从原始模型重新生成

保留 `F:/no-fft/no-fft.tar.gz`（含模型代码和指定 checkpoint）、`F:/no-fft/test/` 的原始 10,000 组样本，
以及需要做光学重建时使用的 `Zeg.npy`。对应来源和哈希见 [来源审查](../reports/source_update_20261125.json)。
按顺序执行下列教程，不依赖任何未公开在线下载地址：

1. [数据划分与 FP32](software_reference.md)：独立 CPU 环境、数据审查、模型解包和参考生成。
2. [量化](quantization.md)：校准、候选比较与导出验证。
3. [末层整数参考](integer_head.md)，再 [两层与 GELU](integer_tail.md)。

若更换源路径、数据或运行环境，应在新的实验/恢复副本中重新生成相关参考与报告，不手工篡改历史哈希以绕过检查。
DDR 工程的重建另需 ACX720-V3 的厂家 ch37/ch38/ch39 等资料，见 DDR 教程。

## 换板时如何继续

保留实验 02 的目录作为已结束基线，新建 `experiments/03_<board>_nofft/`（以实际空闲编号为准），
在新目录 README 链接本页，记录新板卡型号、FPGA/SoC 型号、DDR 容量/带宽、接口和工具版本。
不要沿用本板的 XDC、MIG 配置、时钟假设或 bit。

可以复用：整数数学契约、乘加/重定标 RTL、GELU 数值参考、测试方法、串口协议与数据划分。
需要重新决策：新板的实现工具链、并行度、权重/激活存储、DDR 数据搬运、非线性算子方案与性能目标。
W16A16_M125 是本阶段的候选基线，不是对新板性能或最终精度的保证。
先在新板复现这段已知结果，再扩展计算图，最终用保留的验收集评价完整模型。
