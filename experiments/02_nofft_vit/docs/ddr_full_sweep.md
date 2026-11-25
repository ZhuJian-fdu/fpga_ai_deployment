# 第二阶段：256 MiB DDR 地址覆盖测试

前提：第一阶段校准和低 16 MiB 流量观察已通过（用户于 2026-11-25 反馈）。
第一阶段原始 bitstream 保留在 `build/ddr_test/`，本阶段使用单独的 `build/ddr_full/`。

## 为什么增加这一步

活动灯闪烁只表明有读回，不代表整个内存容量已经覆盖。
本测试按下列固定顺序执行，每轮先写满全部地址，再开始读回：

1. 写入 256 MiB：每个 128 位数据拍的四个 32 位字使用不同常量与字节地址异或。
2. 从头读回 256 MiB，逐拍比较数据、响应 ID、响应码及 RLAST。
3. 将上述数据逐位取反，再完整写入 256 MiB。
4. 再完整读回并比较，通过后锁存完成信号。

这样可以检测测试中暴露的地址重复映射和数据错误。全部写完再读，避免“写一个地址、立即读它”
掩盖高地址映射回低地址的问题。两轮之间数据逐位反相，确保各数据位都写过 0 和 1。

AXI 地址为 28 位**字节地址**，范围 `0x0000000..0xfffffff`。
每拍 16 字节，每个 burst 16 拍（256 字节），最后一个 burst 从 `0xfffff00` 开始，
最后一拍地址是 `0xffffff0`。固定 256 字节对齐的 burst 不跨越 4 KiB 边界。
每轮比较 16,777,216 拍，共比较 33,554,432 拍；总流量为 512 MiB 写、512 MiB 读。

此程序会覆盖 DDR 中现有数据；用于当前独立测试，不执行模型推理，也不写 Flash。
完成两轮不等于长期稳定性、温度/电压裕量或所有存储故障模式均已验证。
这也不是峰值带宽测试：只允许一个事务在途，刻意使用简单的读写状态机。

写地址和写数据分别握手，WVALID 不等待 AWREADY；分别记录两路完成后才处理写响应。
对应 [Arm AXI 协议的通道依赖要求](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/IHI0022H_amba_axi_protocol_spec.pdf)。

## 构建与仿真

复用已核对的 35T MIG 配置及 V3 引脚文件，不再使用厂商流量发生器。
在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\prepare_ddr_test.py
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_ddr_full.py
New-Item -ItemType Directory -Force experiments\02_nofft_vit\build\vivado | Out-Null
Push-Location experiments\02_nofft_vit\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log ddr_full_build.log -source ..\..\scripts\build_ddr_full.tcl
    if ($LASTEXITCODE -ne 0) { throw 'DDR full sweep build failed' }
} finally { Pop-Location }
```

脚本重建 `build/ddr_full/`，运行前关闭 GUI 中同名工程。
仅修改本实验 RTL、保持 IP 配置不变时，可在命令末尾加 `-tclargs --reuse`，
复用已有 IP 生成物并重新综合/实现顶层；若修改 MIG 或时钟配置，必须使用默认完整重建。
仿真使用 Icarus Verilog 的 AXI 行为内存模型，覆盖低地址小窗口、最高地址边界、
等待/复位和故障注入；没有仿真真实 MIG/DDR PHY，也没有模拟全部 256 MiB 的模拟电气行为。
结果见 [仿真记录](../reports/ddr_full_simulation.txt)。

## 下载与灯状态

在 Vivado Hardware Manager → Program Device 选择：

```text
F:\GitHubProjects\fpga_ai_deployment\experiments\02_nofft_vit\build\ddr_full\acx720_v3_ddr_full.bit
```

Debug probes 留空；下载后按一下 S4 并松开，观察 30 秒。
本程序没有串口交互。

| 阶段 | LED0 | LED1 | LED2 |
|---|---|---|---|
| 等待 DDR 校准 | 灭 | 灭 | 灭 |
| 测试进行中 | 闪烁 | 亮 | 灭 |
| 两轮全部通过 | **持续常亮** | **持续常亮** | **灭** |
| 检测到错误或总线超时 | 灭 | 通常仍亮 | **亮** |

与第一阶段不同，LED0 的闪烁是测试期间的心跳，不能单独证明读写活动；
必须等到 LED0 变为持续常亮，才能表示两轮比较全部完成。
通过状态和错误状态保持到 S4 复位；再次按 S4 会从头重新校准并测试。
如果仍在闪烁、LED1 没亮，或 LED2 亮起，请报告实际状态，不把它记为通过。

总线连续没有握手约 1.34 秒（100 MHz UI 时钟下 2^27 周期）会锁存错误。
超时后保留已发出的 AXI VALID；对端恢复时完成当前事务后停止，不启动下一事务。
错误细节信号在测试模块内用于仿真，但本板级版本未导出 UART/ILA，不能仅凭 LED 定位具体地址。

最新状态见 [全容量测试记录](../reports/ddr_full_validation.md)。
