# 第二课：电脑与 FPGA 之间收发字节

前置条件：用户已确认 ACX720-V3 点灯成功。
实测进展：2026-11-24，COM11 上连续两轮、每轮 1296 字节完全一致；用户确认 LED1 常亮、LED2 熄灭、LED0 闪烁。
下一课见 [AI 上板教程](ai_bringup.md)。
本课建立电脑 → 板载 CH340E → FPGA 接收器 → FIFO → FPGA 发送器 → 电脑的回环。
还没有图像协议或模型推理；先确认每一个字节都能可靠传输。

## 1. 接口与参数

原理图第 9 页的 J2 是板载 CH340E 串口 Type-C 接口。
使用带数据传输功能的 USB 线连接该 UART 接口；保持已经成功的下载和供电方式。
如果下载线与 UART 线接在不同接口，可能需要同时连接两条线。
不要因为两个插口外形都是 Type-C 就将串口、USB2.0 实验接口和下载通道混为一谈。

电脑串口参数：**115200 baud，8 个数据位，无奇偶校验，1 个停止位（8N1），无流控**。
FPGA 时钟 50 MHz，每位取 434 个时钟，实际波特率约 115207.37，偏差约 +0.0064%。
UART 空闲为高；一个字节依次发低起始位、低位在前的 8 位数据、高停止位，共 10 位。

V3 引脚表 Sheet1：RX=J21（第 29 行），TX=M15（第 30 行），均 LVCMOS33。
FPGA RX 接 CH340E 的 TXD，FPGA TX 接 CH340E 的 RXD，板上已完成交叉连接，无需杜邦线短接。

## 2. 下载 UART 程序

沿用点灯时的 **Hardware Manager → Auto Connect → Program Device**，选择：

```text
F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/build/uart/acx720_v3_uart.bit
```

没有 ILA，Debug probes file 留空。这次 Program Device 会替换当前 FPGA 中的点灯电路，
新程序仍保留 LED0 心跳；不会改变 Flash 中的出厂程序。

| LED | 含义 |
|---|---|
| LED0 | 每半秒翻转，说明时钟和复位正常 |
| LED1 | 至少收到一个有效字节后常亮，S4 清除 |
| LED2 | 收到错误停止位或 FIFO 溢出后常亮，S4 清除 |

测试前按一下 S4，开始发送后不再按复位。

## 3. 找到正确的 COM 口

在仓库根目录的 PowerShell 运行：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\software\uart_loopback.py --list
```

寻找 CH340/USB-SERIAL 对应的 COM 口。蓝牙 COM 口不是板子。
若不确定，比较 UART 线连接前后的列表，或查看设备管理器“端口（COM 和 LPT）”。
如果没有新增串口，检查 UART 插口、数据线和盘 A 提供的 CH340 驱动。
运行脚本前关闭占用该端口的串口助手。

## 4. 自动核对回环结果

下面的 COM12 只是示例，必须替换为上一步识别的板卡端口：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\software\uart_loopback.py --port COM12
```

脚本依次发送 16 字节文本、0～255 的全部字节值、1024 个固定随机字节，
每次最多发送 64 字节并等待同样数量的回包，逐字节比较，不依赖屏幕上的字符显示。
成功时显示 `PASS: all 1296 bytes match`，并生成 `build/uart_loopback_result.json`。
同时确认 LED1 亮、LED2 灭。再次运行仍应成功。

如果超时，先检查是否下载了 UART 的 `.bit`、COM 口是否正确、UART USB 线是否已连接。
如果 LED2 亮，先保存失败信息，再用 S4 复位重试；不要把清灯当成修复通信错误。

## 5. 读代码与复现

- `rtl/uart_rx.v`：两级输入同步，起始位中心确认，随后逐位采样并检查停止位。
- `rtl/uart_tx.v`：将一个字节串行发送；`valid && ready` 表示接收发送请求。
- `rtl/uart_echo.v`：16 字节 FIFO 暂存收到的数据，避免发送忙时直接覆盖字节。
- `board/acx720_v3_uart_top.v`：连接串口、复位和三个 LED。
- `board/acx720_v3_uart.xdc`：引脚、时钟与异步接口时序约束。

有界 FIFO 不等于无限缓存。持续输入快于输出仍可能溢出；本课 PC 脚本采用最多 64 字节的
分块等待方式，后续图像协议将加入明确的帧长、校验和超时处理。
本课只检查 UART 停止位，没有奇偶校验或帧校验，不能把回环层当作完整可靠图像协议。

本机依赖已装好；新电脑按实验目录 `requirements.txt` 安装。
串口库行为参考 [pySerial 官方 API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)。

复现 RTL 仿真：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py uart
```

创建/打开独立 UART 工程，在 Vivado Tcl Console 中执行：

```tcl
source F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/scripts/create_uart_project.tcl
```

批处理构建（先关闭 GUI 中的同一个 UART 工程）：

```powershell
New-Item -ItemType Directory -Force experiments\01_digits_linear\build\vivado | Out-Null
Push-Location experiments\01_digits_linear\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log uart_build.log -source ..\..\scripts\build_uart.tcl
    if ($LASTEXITCODE -ne 0) { throw 'UART build failed' }
} finally { Pop-Location }
```

GUI 的 Generate Bitstream 默认生成 `acx720_v3_uart.runs/impl_1/acx720_v3_uart_top.bit`，
不会更新上面的固定路径文件；修改代码后请下载本轮构建的文件。

验收：脚本逐字节核对通过，LED2 保持熄灭，记录真实串口验证结果。
完成后下一课再将 64 个像素送入分类核心，并返回预测数字。
