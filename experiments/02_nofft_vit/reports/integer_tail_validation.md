# 两层整数全连接与 GELU 验证记录

日期：2026-11-25。ACX720-V3，XC7A35T-FGG484-2，Vivado 2023.2。
**软件参考、RTL 仿真、综合实现与 bit 生成已通过；本版本 1,000 组实板回读也已通过。**
上一版仅末层的实板通过记录保存在 [串口验收报告](integer_uart_validation.md)，不作为本版本实板通过的依据。

## 数值参考

范围是 `head.4` 的 192→96 全连接、`head.5` GELU、`head.7` 的 96→42 全连接。
两层使用真正整数乘加和整数重定标，GELU 使用全 INT16 地址空间查表。
300 组校准确定新增尺度，1,000 组开发数据比较误差，8,700 组预留数据未使用。

- 两层重定标与独立精确分数比例舍入比较，输出码差异均为 0。
- 65,536 项 GELU 表与独立 PyTorch float64 GELU 量化结果比较，输出码差异为 0。
- 开发样本中两层重定标及 GELU 均无饱和，无 48 位累加溢出。
- 相对原 Q/DQ 模型的有效位置 RMSE 为 0.0000123033，相对 FP32 为 0.0000864291。
- 相对标签的 masked RMSE 为 0.1026577965。该数字属于当前软件开发集结果，不是新的全模型实板精度。

详见 [参考报告](integer_tail_reference.json) 和 [整数契约说明](../docs/integer_tail.md)。

## RTL 仿真

1. 16 组实时替换的 192 维输入：比较 1,536 个中间累加值、重定标码和 GELU 码，
   以及 672 个最终输出记录；验证输出暂停时稳定、复位中止和恢复。
   [仿真报告](integer_tail_simulation.json)、[原始输出](integer_tail_simulation.txt)。
2. 串行 RX/TX 引脚仿真：5 次事务、1,925 个响应字节逐字节匹配，包含正常计算、
   错误 CRC 拒收、部分帧超时恢复及复位。仿真 8 周期/位，硬件 434 周期/位。
   [串口仿真报告](integer_tail_uart_simulation.json)、[原始输出](integer_tail_uart_simulation.txt)。

## 构建结果

| 项目 | 结果 |
|---|---|
| 时钟 | 50 MHz |
| WNS / WHS / WPWS | 5.717 / 0.036 / 8.870 ns |
| Setup / Hold / Pulse-width 失败端点 | 均为 0 |
| LUT | 2,292 / 20,800（11.02%） |
| 寄存器 | 727 / 41,600（1.75%） |
| BRAM Tile | 50 / 50（100%） |
| DSP | 14 / 90（15.56%） |
| DRC | 0 Error、0 Critical Warning、24 Warning |
| CDC | 2 Safe、0 Unsafe、0 Unknown、0 No ASYNC_REG |
| ROM 初始化 | 九个参数/查表 MEM 文件全部确认成功读取 |
| 内部未约束端点 / 无时钟 / 组合环 | 均为 0 |

DRC 的 24 个提示为 DPIP-1 两项、DPOP-1 八项、DPOP-2 十四项；Methodology 有十二个
SYNTH-10 宽乘法器提示。综合最初推断超出 BRAM 容量，产生 Synth 8-5835，并将部分存储实现为 LUT RAM；
最终实现使用 50 个 BRAM Tile，未超出器件资源，时序及阻断级 DRC 检查通过。
保留原始告警，未屏蔽或降低级别。资源已无 BRAM 余量，后续扩展必须重新规划存储。
S4/UART RX 的 false path 只到第一级同步器；LED/UART TX 为异步对外接口。

bit 文件：`build/integer_tail_hw/acx720_v3_integer_tail.bit`。
源码、参考、MEM、bit、仿真和构建报告的哈希见 [构建清单](integer_tail_build_manifest.json)。
此次构建没有连接或烧写板子；用户随后确认下载完成，通过下述真实串口回读验收。

## 实板回读结果

2026-11-25 15:04（北京时间），通过 USB-SERIAL CH340 的 COM10 端口，以 115200 波特率
完成 1,000 组开发集 192 维整数输入的实板计算。42,000 个最终输出记录的末层 48 位累加值、
INT16 结果、饱和及计算错误标志全部与软件整数参考逐项一致。
全部响应通过帧格式、序号及 CRC 校验，失败列表为空，没有末层输出饱和或计算错误标志。
总耗时 171.859 秒，包含主机、串口传输和比较开销，不能作为 FPGA 纯计算延迟。

原始结果：[实板回读 JSON](integer_tail_uart_hardware.json)。
串口设备、测试命令、参考和程序哈希：[验收关联记录](integer_tail_acceptance.json)。
关联 bit 文件以用户下载确认为依据，未独立读取板上配置身份。
构建清单中的 `physical_validation: pending` 保留构建时状态，当前验收结果以本报告为准。

板上执行 `head.4 → GELU → head.7`，中间结果不经过电脑；本协议只回读最终 42 个记录，
没有独立回读中间 96 维值。前面的网络仍由电脑生成输入，8,700 组预留集未使用。
本阶段通过不等同于完整网络上板或预留集最终精度验收。

复现使用 `check_integer_tail_board.py`，不可使用上一版 96 维输入的主机程序。
具体步骤见 [教程](../docs/integer_tail.md)。
