# DDR 全容量地址覆盖测试记录

日期：2026-11-25。板卡 ACX720-V3，FPGA `xc7a35tfgg484-2`。

## 前置证据

用户已确认第一阶段 LED0 闪烁、LED1 常亮、LED2 熄灭。
见 [实板观察记录](ddr_hardware_observation.json)；该结果只覆盖初步运行，不能推断全容量通过。

## 本阶段检查

- 自编固定 128 位 AXI 主机，覆盖 28 位字节地址范围，两轮地址相关数据/反相数据写后读比较。
- 每轮先写满再读，检查响应码、响应 ID、RLAST、读数据和事务无进展超时。
- 16 项行为仿真通过，包括随机等待、最高地址、复位重测、数据错误、地址别名、
  错误响应/ID、RLAST 错误、超时及超时后的事务完成行为，
  以及从机等待 WVALID 才接受地址、数据早于地址被接收两种写通道次序。
- 行为仿真使用小范围内存和最高地址窗口；不是完整 DDR PHY 仿真或物理内存验证。
- 构建状态：Vivado 2023.2 最终版本于 2026-11-25 13:40（本机 Asia/Shanghai）完成，退出码 0。
  最后一次构建复用未改动的 MIG/时钟 IP，重新综合、布局布线本实验顶层及测试逻辑。
  实板状态：**两轮全地址比较通过（2026-11-25 用户反馈）**。

## 最终构建结果

| 项目 | 结果 |
|---|---|
| WNS / TNS | 0.982 ns / 0 ns |
| WHS / THS | 0.041 ns / 0 ns |
| WPWS / TPWS | 0.000 ns / 0 ns |
| LUT | 5,825 / 20,800（28.00%） |
| 寄存器 | 4,926 / 41,600（11.84%） |
| BRAM / DSP | 0 / 0 |
| 最终 DRC | 0 Error，0 Critical Warning，3 Warning |
| IP | MIG 4.2、Clocking Wizard 6.0 均 Up-to-date |
| 时钟缺失 / 内部未约束端点 / 组合环 | 均为 0 |
| CDC | Unsafe、Unknown 均为 0；2 项外部输入域 Warning / No ASYNC_REG |

三条 DRC Warning 仍为 MIG 内部 `BUFC-1` 两项及 `REQP-1709` 一项。
Methodology 仍有 `LUTAR-1`、`XDCB-5` 各一项 Warning，`REQP-1959` 16 项 Advisory。
S4/LED false path 和 DDR 异步复位输出缺少普通同步 output delay 的边界保持不变，
详见 [第一阶段警告记录](ddr_validation.md)。未屏蔽或降低任何规则严重性。
这些结果不是零警告验收，也不代表完整板级时序/电气验证。

构建文件、配置、仿真记录及 bitstream 哈希见 [最终构建清单](ddr_full_build_manifest.json)。
详细工具报告保留在本地 `build/ddr_full/`。原始第一阶段 bitstream 哈希已复核，保持不变。

## 实板验收结果

下载 `build/ddr_full/acx720_v3_ddr_full.bit`，按下并释放 S4，观察 30 秒：
最终应为 **LED0 持续常亮、LED1 持续常亮、LED2 熄灭**。
此状态表示该次运行完成两轮数据比较；尚不能代替多次复位测试、长时间压力测试和带宽测量。

操作步骤：[全容量测试教程](../docs/ddr_full_sweep.md)。

用户反馈：按下并释放 S4 后，LED0 先闪烁，随后持续常亮；LED1 始终亮，LED2 始终灭。
与程序从运行到通过的状态转换一致。该次测试覆盖 256 MiB 地址范围，每轮先写满再读回，
共两轮、512 MiB 写入和 512 MiB 读回比较。证据来自用户观察，没有独立串口计数器读数，
精确耗时未测量。[实板反馈与对应 bitstream 哈希](ddr_full_hardware_observation.json)。
构建清单中的 pending 是构建时状态，本记录补充后续实板结果；不修改历史构建清单。
