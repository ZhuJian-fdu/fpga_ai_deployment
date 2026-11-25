# 最后一个 Linear 层的整数硬件验证

2026-11-25，ACX720-V3 / `xc7a35tfgg484-2`。

软件完成 1,000 组末层整数参考；RTL 完成 124 组边界/随机点积和 672 组真实向量对照，
错误注入及复位重测通过。依据分别见 [软件报告](integer_head_reference.json) 和 [仿真报告](integer_head_simulation.json)。

当前构建状态：Vivado 2023.2 已于 2026-11-25 14:28 完成最终 bitstream（退出码 0）。
实际板卡状态：**固定向量自检通过（2026-11-25 用户反馈）**。
用户确认 LED0 常亮、LED1 闪烁、LED2 熄灭；没有独立串口读数。
对应 bitstream 和观察来源见 [实板记录](integer_head_hardware_observation.json)。
构建清单的 pending 保留为构建时状态。

| 检查 | 结果 |
|---|---|
| 时钟 | 50 MHz |
| WNS / TNS | 5.282 ns / 0 ns |
| WHS / THS | 0.130 ns / 0 ns |
| WPWS / TPWS | 9.500 ns / 0 ns |
| LUT | 851 / 20,800（4.09%） |
| 寄存器 | 229 / 41,600（0.55%） |
| BRAM Tile | 6 / 50（12%），包含输入、权重与期望结果 ROM |
| DSP | 7 / 90（7.78%），包含点积与宽乘数重定标 |
| 最终 DRC | 0 Error、0 Critical Warning、13 Warning |
| ROM 初始化 | 八个 `.mem` 均成功读取；无 malformed readmem 或未驱动信号警告 |
| 内部未约束端点 / 无时钟 / 组合环 | 均为 0 |
| CDC | 外部 S4 同步链报告 Safe，Unsafe/Unknown/No ASYNC_REG 均为 0 |

13 条 DRC Warning 为 DSP 流水线提示：`DPIP-1` 两项、`DPOP-1` 四项、`DPOP-2` 七项。
Methodology 另有 `SYNTH-10` 六项宽乘法器提示。当前 50 MHz 时序满足，未屏蔽或降级规则；
后续提高频率、降低功耗或优化重定标资源时需要重新评估流水线。
S4 输入与三路 LED 是异步人机接口，使用 false path，不代表这些引脚具有同步输入/输出延迟约束。

资源占用属于本阶段固定向量的末层自检实例，不能按比例外推整网资源或推理速度。
最终源码、向量和下载文件哈希见 [构建清单](integer_head_build_manifest.json)。

本程序只计算最终的 96→42 层，前序网络不在 FPGA 上执行。
输入与期望结果预存在片内 ROM；验收覆盖固定的 16 组输入。

下载教程：[整数末层自检](../docs/integer_head.md)。
