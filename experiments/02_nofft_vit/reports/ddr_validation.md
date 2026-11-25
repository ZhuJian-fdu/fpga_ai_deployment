# DDR3 阶段验证记录

日期：2026-11-25。ACX720-V3 / `xc7a35tfgg484-2`。

## 已完成

- 收到并检查 ch37、ch38、ch39 三个厂商工程压缩包，原文件未修改。
- ch37 同时包含 100T/35T 配置，选择 35T 的 `mig_b.prj`。
- 48 个 DDR 管脚与独立 V3 UCF 一致；原理图第 1、4 页确认 Bank34 接线和 DDR 1.5 V 供电。
- 使用本仓库顶层/XDC 替代归档里混用的旧复位/指示灯约束；时钟和 DDR 时序由重新生成的 IP 约束。
- 添加读回活动指示与锁存错误指示，复用厂商 MIG AXI 测试发生器。

## 当前状态

Vivado 2023.2 已完成综合、布局布线和 bitstream 生成；准备脚本重跑后，七个生成输入文件逐字节一致。
可下载文件：`../build/ddr_test/acx720_v3_ddr_test.bit`。
用户已下载并反馈三路 LED 与预期一致，初步校准/读写观察通过。没有执行完整 DDR 存储器模型仿真。

| 检查 | 结果 |
|---|---|
| 建立时间 WNS / TNS | 0.982 ns / 0 ns |
| 保持时间 WHS / THS | 0.039 ns / 0 ns |
| 脉宽 WPWS / TPWS | 0.000 ns / 0 ns |
| LUT | 6,252 / 20,800（30.06%） |
| 寄存器 | 5,631 / 41,600（13.54%） |
| BRAM / DSP | 0 / 0；本测试不代表未来模型资源占用 |
| 最终 DRC | 0 Error，0 Critical Warning，3 Warning |
| IP 状态 | MIG 4.2、Clocking Wizard 6.0 均 Up-to-date |
| 无时钟 / 内部未约束端点 / 组合环 | 均为 0 |
| CDC 报告 | Unsafe、Unknown 均为 0；仍有 2 项外部输入域 Warning / No ASYNC_REG |

### 保留的警告及约束边界

- DRC `BUFC-1` 两项：MIG 的两个 DQS 差分 I/O 宏内存在无负载的输入缓冲分支。
  已定位到生成的 PHY 包装模块；不能据此推断整个 DQS 未连接，也不视为已验证无害。
- DRC `REQP-1709` 一项：MIG 内部 PLL 输出采用不同类型负载，工具提示不能保证这些输出相位对齐。
  已核对生成的 infrastructure RTL 和布线后连接：CLKOUT3 接 BUFH，其他输出包含 BUFG 和 PHASER。
  本阶段保留原 IP 实现，不自行更换缓冲或屏蔽该警告；仍需实板校准、读写和后续压力验证。
- Methodology 另有 `LUTAR-1` 一项（MIG 内部复位逻辑）、`XDCB-5` 一项（MIG 约束查询效率），
  以及 `REQP-1959` 16 项 Advisory（MIG 内部 SERDES 复位驱动）。这些不计入上面的三条 DRC Warning。
- `check_timing` 中外部 S4 输入和三路 LED 使用 false path；DDR 的异步复位输出 `ddr3_reset_n`
  未设普通同步输出延迟，工具将其列为 no_output_delay。所报时序通过仅覆盖已有约束，
  不等于已经检查所有外部异步复位时序或验证复位释放行为。
- 未降低规则严重性、未添加警告豁免、未改写生成的 MIG RTL。IP 状态正常不能代替板级验证。

### 复核文件与下一步

本机构建目录保留 `timing_summary.rpt`、`utilization.rpt`、`drc.rpt`、`cdc.rpt`、
`check_timing_verbose.rpt`、`methodology.rpt`、`ip_status.rpt` 和 `io.rpt`（目录被 Git 忽略）。
版本归档保留 [构建清单与文件哈希](ddr_build_manifest.json) 和本文摘要。

下载后按下并释放 S4，观察至少 30 秒：LED1 常亮、LED0 持续闪烁、LED2 熄灭，
才可记录本阶段初步读写观察通过。当前测试窗口为低 16 MiB，不能证明全部 256 MiB 容量正确。
用户实板观察结果（2026-11-25）：**初步通过（用户反馈）**。LED0 持续闪烁、LED1 常亮、LED2 熄灭。
依据为用户回复“灯的状态与预期一致”，未独立读取硬件计数器，未记录精确持续时间。
该结果不构成全容量验证、长期稳定性证明或对工具警告的全面豁免。

独立归档：[实板反馈与对应 bitstream 哈希](ddr_hardware_observation.json)。
构建清单中的 pending 保留为构建时点状态，以本次观察记录补充后续结果。
下一阶段：[256 MiB 地址覆盖测试](../docs/ddr_full_sweep.md)。

教程：[DDR 初步测试](../docs/ddr_bringup.md)。
