# 串口整数末层验证记录

日期：2026-11-25。板卡：ACX720-V3，器件：XC7A35T-FGG484-2。

前一版本固定 16 组输入、672 个输出的板上自检，已由用户观察 LED 确认通过，
见 [原始反馈记录](integer_head_hardware_observation.json)。
本记录对应新的实时串口输入版本，**实板串口回读已通过：1,000 组输入、42,000 个输出记录逐项一致**。

## 仿真

Icarus Verilog 仿真通过。测试真实 RTL 串行 RX/TX 引脚，5 次事务共逐字节比较 1,925 字节响应，
其中 4 组正常输入、1 组损坏请求 CRC；覆盖输入替换、CRC 拒收、部分帧超时恢复、
错误锁存及复位清除。结果与软件生成的整数参考比较，包含累加值、量化值、标志和响应 CRC。
串口仿真采用 8 周期/位加速，硬件采用 434 周期/位；物理传输已由下述实板回读验证。
见 [仿真摘要](integer_uart_simulation.json) 和 [原始输出](integer_uart_simulation.txt)。

## Vivado 2023.2 构建

| 项目 | 结果 |
|---|---|
| 时钟 | 50 MHz，20 ns |
| WNS / WHS / WPWS | 5.894 / 0.036 / 8.870 ns |
| Setup / Hold / Pulse-width 失败端点 | 均为 0 |
| LUT | 1,165 / 20,800（5.60%） |
| 寄存器 | 399 / 41,600（0.96%） |
| BRAM Tile | 4 / 50（8.00%） |
| DSP | 7 / 90（7.78%） |
| DRC | 0 Error、0 Critical Warning、13 Warning |
| CDC | 2 Safe、0 Unsafe、0 Unknown、0 No ASYNC_REG |
| ROM 初始化 | weights、biases、multipliers、shifts 均成功读入 |
| 内部未约束端点 / 无时钟 / 组合环 | 均为 0 |

DRC 的 13 个 Warning 为 DSP 流水线提示：DPIP-1 两项、DPOP-1 四项、DPOP-2 七项。
Methodology 有 SYNTH-10 宽乘法器提示六项。综合另有并行综合条件未满足及优化未使用寄存器位的提示。
当前频率下时序通过；未降低告警等级。S4、UART RX 仅到第一级同步器使用 false path，
LED/UART TX 为异步对外接口，未设置同步输出延迟。

bit 文件为 `build/integer_uart_hw/acx720_v3_integer_uart.bit`。
源码、系数、bit 和报告 SHA-256 见 [构建清单](integer_uart_build_manifest.json)。
构建脚本未连接或烧写 FPGA；用户随后确认已下载，通过真实 UART 完成下述验收。

## 实板验收结果

2026-11-25 14:49（北京时间），通过 USB-SERIAL CH340 的 COM10 端口、115200 波特率，
完成 1,000 组开发集隐藏向量回读。全部 42,000 个输出的 48 位累加值、INT16 输出、
饱和及运算错误标志与软件参考逐项相同；全部响应通过序号、帧格式及 CRC 校验。
无饱和、无运算错误，失败列表为空，总耗时 154.593 秒。
该耗时包含电脑端、串口和逐项比较，不能作为 FPGA 纯计算延迟。

原始脚本结果：[实板回读 JSON](integer_head_uart_hardware.json)。
本次测试的文件及设备信息：[验收关联记录](integer_uart_acceptance.json)。
关联 bit 文件以用户下载确认为依据，未独立读取板上配置身份。
构建清单中的 `physical_validation: pending` 保留构建时状态，当前实板结果以本报告为准。
复现命令见 [串口操作说明](../docs/integer_uart.md)。

范围仅为 `head.7` 的 96 → 42 层。前面的网络在电脑上执行，不使用本版本之外的 DDR 自检结果
推断模型正确性；8,700 组预留验收集未参与本次仿真和硬件测试准备。
