# ACX720-V3 第一课：下载我们自己的点灯程序

目标：LED0 每半秒翻转一次；按住 S4 熄灭，松开后重新开始计时。
本次已完成代码仿真、综合、布局布线和 bitstream 生成。
用户于 2026-11-24 确认点灯实验成功。下一步见 [UART 回环教程](uart_loopback.md)。

## 1. 打开工程并看懂文件

Vivado 2023.2 → Open Project，选择：

```text
experiments/01_digits_linear/build/heartbeat/acx720_v3_heartbeat.xpr
```

以上路径相对仓库根目录。文件不存在时，在 Vivado Tcl Console 输入：

```tcl
source F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/scripts/create_heartbeat_project.tcl
```

Sources 中：

- `acx720_v3_heartbeat_top.v`：顶层，连接三个外部端口，处理复位的同步释放。
- `heartbeat.v`：每计数 25,000,000 个时钟翻转一次 LED。50 MHz 时每个时钟为 20 ns，因此翻转间隔 0.5 秒。
- `acx720_v3_heartbeat.xdc`：将 clk/reset_n/led0 绑定到 Y18/B21/M22，并声明 20 ns 时钟。

逻辑端口名由我们命名；真正接哪一个封装管脚由 XDC 决定。
默认 CLK_HZ=50,000,000。仿真把它改为 8 以缩短等待，但实际构建保持 50 MHz。

## 2. 沿用以前成功下载的连接

用户确认以前用一条 USB-Type-C 线在 Vivado 下载过自己编译的 `.bit`，先沿用那套接线和开关位置。
当前资料中的 J2 是 CH340E 串口，J5 是 USB2.0 接口，P1 是独立 10 针 JTAG。
接口外形本身不能证明下载链路；本轮以 Vivado 是否实际检测到 `xc7a35t` 为准。
不需要仅因示意图存在 P1 就先购买外置下载器。

本工程按配套引脚表使用 LVCMOS33；如果曾修改可调 I/O 电源 VCCIO / P6，先确认恢复匹配的 3.3 V 配置。

## 3. 在 Hardware Manager 下载

1. 点击 **Open Hardware Manager**。
2. 点击 **Open Target → Auto Connect**。
3. Hardware 列表应出现 **xc7a35t**。如果只有 COM 口，不能据此认定 Vivado 已连接 FPGA。
4. 右键 FPGA → **Program Device**。
5. Bitstream file 选择：

```text
F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/build/heartbeat/acx720_v3_heartbeat.bit
```

6. 这个程序没有 ILA，Debug probes file 留空。点击 **Program**。
7. 观察拨码开关 0 附近的 **LED0/D0**（不是电源灯或 DONE 灯）：应灭半秒、亮半秒，持续循环。
8. 按住 **S4**：LED0 熄灭。松开 S4：从熄灭状态重新计时，约半秒后点亮。

只有上述实际现象验证通过，才能记录“本次点灯上板成功”。
这是 FPGA 易失配置；断电后可能恢复原先的出厂程序。本次不操作配置 Flash。

## 4. 如需自己重新构建

Vivado 左侧依次 **Run Synthesis → Run Implementation → Generate Bitstream**。
GUI 生成的文件通常位于：

```text
build/heartbeat/acx720_v3_heartbeat.runs/impl_1/acx720_v3_heartbeat_top.bit
```

GUI 构建不会更新上面脚本生成的 `build/heartbeat/acx720_v3_heartbeat.bit`。
修改代码后，必须选择本轮构建生成的文件，避免下载旧程序。

也可以从仓库根目录在 PowerShell 运行脚本，自动更新固定路径文件：

```powershell
Push-Location experiments\01_digits_linear\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log heartbeat_build.log -source ..\..\scripts\build_heartbeat.tcl
    if ($LASTEXITCODE -ne 0) { throw 'Build failed; inspect heartbeat_build.log' }
} finally { Pop-Location }
```

运行脚本前关闭 GUI 中同一个工程。新克隆仓库若无 `build/vivado`，先创建该目录。
脚本重新综合、布局布线，检查 setup/hold 与阻塞级 DRC 后生成 `.bit`；不连接板卡或自动下载。

## 5. 记录结果与下一步

记录 LED0 周期、S4 复位现象，以及 Hardware Manager 识别的器件和下载目标。
随后学习 UART 回环，再把 64 像素输入和数字分类结果接入串口。
完整资料核验和构建结果见 `reports/heartbeat_validation.md`。
