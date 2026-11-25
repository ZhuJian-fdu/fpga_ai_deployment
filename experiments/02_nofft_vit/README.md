# 实验 02：no-FFT PSF 模型的 FPGA 分段部署

**状态：ACX720-V3 教学阶段已结束，2026-11-25 归档。**
按用户决定，本模型在此教学板上的部署到此为止；以后更换性能更好的板卡再继续。
这是一份分段部署的学习与验证记录，**不是完整模型已上板的工程**。

模型为 Coordinate Attention + CBAM + ViT-Small + MLP，输入 `[5,112,112]`，输出 42 个系数。
板卡 ACX720-V3，FPGA `xc7a35tfgg484-2`。详见 [阶段结束与换板交接](docs/project_closeout.md)。

## 最终完成范围

| 阶段 | 结果与证据 |
|---|---|
| DDR3 独立测试 | 256 MiB 全容量地址/反码比较，用户反馈 LED 符合预期；[记录](reports/ddr_full_validation.md) |
| 数据和 FP32 基线 | 固定 300 校准 / 1,000 开发 / 8,700 预留；[记录](docs/software_reference.md) |
| 训练后量化 | 选择 W16A16_M125，导出与重新加载验证通过；[记录](docs/quantization.md) |
| 单独末层 | 96→42 整数计算，1,000 组、42,000 个记录逐项匹配；[记录](reports/integer_uart_validation.md) |
| 最终两层段 | **192→96 → GELU → 96→42**，1,000 组、42,000 个最终记录实板逐项匹配；[记录](reports/integer_tail_validation.md) |

最终段运行在 50 MHz，占 14 DSP、50/50 BRAM Tile、2,292 LUT。
实板串口总耗时 171.859 秒，包含电脑、传输与核对开销，不代表 FPGA 纯计算延迟。
前面各层仍在电脑执行；DDR 独立测试尚未接入推理。完整网络整数化、整网实板推理和预留集最终验收未完成。

## 目录与阅读顺序

```text
board/        板级顶层和引脚约束；vendor/ 仅本地存放
rtl/          整数乘加、GELU 查表串联、串口、DDR 测试逻辑
sim/          Verilog/SystemVerilog 仿真
software/     串口协议与实板比较程序
scripts/      资料准备、参考生成、量化、构建、仿真与本地打包
tests/        量化数值测试
docs/         教程、历史背景及结束交接
reports/      本次实验的历史证据和哈希清单
build/        生成文件、模型、参数、向量、bit；不提交
artifacts/    本地复现备份包；不提交
```

1. [结束说明、恢复方式与换板续接](docs/project_closeout.md)
2. [两层全连接与 GELU 教程](docs/integer_tail.md)
3. [完整验证记录](reports/integer_tail_validation.md)与[实板原始结果](reports/integer_tail_uart_hardware.json)
4. [模型背景与早期审查](docs/model_background.md)
5. 历史步骤：[DDR](docs/ddr_bringup.md)、[全容量 DDR](docs/ddr_full_sweep.md)、[整数末层](docs/integer_head.md)、[末层串口](docs/integer_uart.md)

## 归档与复现边界

GitHub 保存源码、教程和小型报告。原始模型/权重、测试数据、厂家资料、Python 环境与生成文件不上传。
仅克隆仓库可以阅读源码和证据，**不能凭空恢复未公开的模型、数据或 bit 文件**。
同机保留的 `build/` 或另存的本地复现包，可恢复本次分段仿真和实板回读所需参数；
从原模型重新生成则还需要原始资料，见 [恢复入口](docs/project_closeout.md)。

UART RTL 复用实验 01 的 `uart_rx.v` / `uart_tx.v`，请保留整个仓库目录。
`reports/` 中的 `pending`、`not_yet_tested` 是当时生成报告时的状态；最终阶段结论以
[结束记录](reports/closeout.json)和[两层实板报告](reports/integer_tail_uart_hardware.json)为准。
历史教程中的“下一步”保留为学习路线，本板不再继续实现这些步骤。
