# 第一阶段：验证 ACX720-V3 的 DDR3

这一步运行独立 DDR3 读写测试，不运行神经网络。模型的权重和激活需要外部存储，
因此先确认存储器控制器能够校准、实际读写并比较数据。

## 资料与适配

商家 `ch37_acx720_ddr_test.rar` 提供 MIG 和 AXI 测试发生器；`ch38` 提供双端口封装，
`ch39` 提供串口到 DDR3 的应用参考。本阶段只使用 `ch37` 的 35T 配置。

- `mig_a.prj` 是 100T 配置；选择 `mig_b.prj` 的 `xc7a35t-fgg484/-2`。
- 48 个 DDR 管脚与此前取得的 V3 `ddr3_pin_.ucf` 完全一致，并核对 V3 原理图第 1、4 页。
- 内存总线 x16，400 MHz DDR 时钟（800 MT/s）；MIG 输入 200 MHz，AXI 数据宽度 128 位。
- 板载 50 MHz 经 Clocking Wizard 生成 200 MHz，锁定后才释放 MIG 低有效复位。
- 新顶层使用 S4=B21、LED0=M22、LED1=N22、LED2=L21。
  厂商归档中部分旧约束使用 F15 复位或 L6/N5 状态输出，本工程不加载这些旧顶层约束。
- 图纸 DDR 器件为 MT41K128M16JT-125:K，供电网为 VCC1V5_DDR3；
  沿用厂商匹配的 MT41J128M16XX-125 / 1.5 V 时序配置，实际初始化结果仍需上板确认。

原始厂商文件只保留在 Git 忽略目录中；准备脚本提取指定文件到 `build/ddr_sources/`，
保留原版权说明，另增加实际读回活动计数和错误锁存输出。未更改 AXI 流量生成及比较逻辑。
文件哈希和引脚比较见 [资料核验记录](../reports/ddr_source_audit.json)。

## 本地构建

需要 Windows 的 `tar`、实验 01 的 Python 环境、Vivado 2023.2。
厂商压缩包放到 `board/vendor/`；独立 V3 引脚 UCF 保留在实验 01 的 `board/vendor/`。
从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\prepare_ddr_test.py
New-Item -ItemType Directory -Force experiments\02_nofft_vit\build\vivado | Out-Null
Push-Location experiments\02_nofft_vit\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log ddr_build.log -source ..\..\scripts\build_ddr_test.tcl
    if ($LASTEXITCODE -ne 0) { throw 'DDR build failed; inspect ddr_build.log' }
} finally { Pop-Location }
```

脚本重建 `build/ddr_test/` 工程，因此先关闭 GUI 中的同名工程。
不要手工修改该生成目录来保存长期变更；修改本实验源码或脚本后重建。
构建不会连接板卡，也不会下载或修改 Flash。

## 下载与观察

本次已生成 bitstream，受约束路径时序通过，最终 DRC 无 Error/Critical Warning；
保留的 3 条 MIG 内部 Warning 及其他检查边界见 [DDR 验证记录](../reports/ddr_validation.md)。
在 Vivado Hardware Manager → Program Device 选择：

```text
experiments/02_nofft_vit/build/ddr_test/acx720_v3_ddr_test.bit
```

Debug probes 留空。本程序没有串口交互；无需启动数字识别或串口回环脚本。
保持已验证的板卡供电和下载连接，下载后按一下 S4，松开后观察至少 30 秒。

| LED | 本阶段含义 |
|---|---|
| LED0 | 每接收 2^22 个 AXI 读数据拍翻转一次；持续闪烁表示读回活动在推进，频率不固定 |
| LED1 | MIG 校准完成后亮起 |
| LED2 | 测试发生器检测到数据/读写/命令错误后锁存为亮，S4 可复位 |

初步预期为 LED1 常亮、LED0 持续闪烁、LED2 熄灭。
LED1 亮而 LED0 长期不变化，不能记为读写测试通过；只校准成功不足以证明数据通路正常。
LED2 亮时先记录现象，再复位重试；复位清灯不代表问题已修复。

## 验收边界

厂商测试发生器当前地址窗口是 `0x00000000..0x00ffffff`（低 16 MiB），含数据比较。
活动计数不是地址覆盖计数，因此不能据此声称已经逐字节验证全部 16 MiB 或整个 256 MiB 容量。
这一步只做上板初步检查；后续需增加确定性的全容量/地址别名测试、长时间压力测试和带宽统计，
再作为模型存储使用。本阶段也没有验证量化模型的数值精度。

最新构建和实物状态见 [DDR 验证记录](../reports/ddr_validation.md)。
