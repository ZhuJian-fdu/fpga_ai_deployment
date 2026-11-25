# ACX720-V3 点灯构建验证

日期：2026-11-24（Asia/Shanghai）。工具：Vivado 2023.2，器件：xc7a35tfgg484-2。

## 资料证据

仅采用用户下载的 V3 材料，没有套用 V1/V2 文件。

| 文件 | SHA-256 |
|---|---|
| ACX720-V3管脚分配表2024_11_13.xlsx | e5381eb9ad8e01df113302e986531876469a964d3e2217ab186277af538ea58a |
| ACX720-V3-SCH.pdf | f9ed1c8428361eefd2f9f20f68c2448b741fc997c96e3b5b169ee9e9b884847a |

表格 Sheet1 第 2/4/27 行和原理图第 1/2/10 页相互核对：
clk=Y18（50 MHz）、led0=M22（高有效）、reset_n=B21（S4 低有效）。
原理图第 3/12 页核对 I/O 电源：本工程假定 Bank16 的可调 VCCIO 保持 3.3 V 配置。
第 9 页 CH340E 串口电路与表第 29/30 行一致，供后续 UART 使用。
原理图已渲染检查；临时抽取文本和图像位于被 Git 忽略的 `build/board_review/`。

## 验证结果

| 检查 | 结果 |
|---|---|
| 板级 testbench | PASS：配置初值启动、S4 复位、两级同步释放、LED 翻转周期 |
| 综合与布局布线 | PASS |
| 50 MHz setup WNS / TNS | 16.242 ns / 0 ns |
| hold WHS / THS | 0.130 ns / 0 ns |
| pulse width WPWS / TPWS | 9.500 ns / 0 ns |
| 资源 | 9 LUT、28 寄存器、1 BUFG、0 DSP、0 BRAM |
| bitstream 生成 | PASS，2,192,131 字节 |

输出：`build/heartbeat/acx720_v3_heartbeat.bit`。
完整时序、DRC、CDC 和资源报告位于同目录。
时序例外仅涉及外部异步复位输入和没有同步接收端的 LED 输出，内部计数与同步释放路径正常计时。
CDC 报告不把无 input delay 的异步输入视为完整分析对象，不能以该报告代替复位同步结构审查。

## 实物状态

用户确认过去曾用一条 USB-Type-C 线在 Vivado 下载自己编译的 `.bit`。
用户于 2026-11-24 回复“点灯实验成功了”，据此将本阶段记为实物验证成功（用户确认）。
没有取得逐项测量记录，因此不额外声称测得精确周期或单独记录了 S4 按键表现。
下一步进行 UART 回环验证。
这份报告仅针对点灯工程；不表示 AI 推理已上板，也不表示 AI 核心完成布局布线。
