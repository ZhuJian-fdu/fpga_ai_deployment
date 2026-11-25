# 第五阶段：最后一层的整数乘加、重定标与上板自检

本阶段实现 `head.7`，即模型最后的 **96 → 42 Linear 层**。
前面的网络仍在电脑上按 W16A16_M125 的 Q/DQ 参考运行；提取其末层输入后，
在软件和 RTL 中执行真正的整数运算。它是整网部署的中间验收，不是整个网络已在 FPGA 上推理。

## 整数运算规则

```text
acc = bias_int48 + sum(input_int16[i] * weight_int16[o,i])
product = acc * multiplier[o]
output_int16 = saturate(round_to_nearest_even(product / 2^shift[o]), -32767, 32767)
```

- 96 项点积采用有符号 48 位累加；偏置由上一阶段的 int64 存储格式检查后缩为 int48。
- MAC 溢出时按二进制补码回绕并锁存错误；自检遇到错误不会报告通过。
- 尺度比例 `input_scale * weight_scale[o] / output_scale` 用正整数乘数和右移近似。
  乘数最多 31 个有效位，本层各通道右移 47～49 位。RTL 接口预留 unsigned 32 位乘数。
- 先对乘积绝对值做最近偶数舍入，再恢复符号，保证负数半格也按相同规则处理。
  最后饱和到 `[-32767,32767]`，另输出饱和标志。
- 乘加和重定标之间有寄存器级；接口支持输入空拍及输出反压，结果在接收前保持。
- 板级实例工作在 50 MHz，S4 经三级同步后复位。没有使用 UART、DDR 或 Flash。

输出尺度只用 300 组校准样本确定，并保留 25% 范围余量：
`output_scale = 2.2181399603382176e-5`。
未来上位机还原系数的关系为 `coefficient = output_int16 * output_scale`。

## 软件与 RTL 验证

在固定的 1,000 组开发样本上：

| 项目 | 结果 |
|---|---:|
| 末层整数输出数 | 42,000 |
| 乘数/移位输出与原尺度精确有理数参照的编码差异 | 0 个 |
| 输出饱和 | 0 个 |
| 实际最大累加绝对值 | 4,288,506,692 |
| 保守累加绝对上界 | 104,652,379,211 |
| 整数累加后反量化与原 Q/DQ 末层的最大差异 | 2.1751e-7 |
| 加上 int16 输出重定标后的最大差异 | 1.1155e-5 |
| 末层整数化额外 RMSE（相对 Q/DQ，39 个有效位置） | 6.4067e-6 |
| 整体输出相对原 FP32 的 RMSE（前序层仍 Q/DQ） | 8.6219e-5 |

实际累加值已超过 signed int32 范围。本层保守界需要 38 个有符号位，采用 48 位以便后续复用。
“编码差异为零”是本批 42,000 个输出的实测结果，不保证任意未来输入的比例近似永远没有一格差异。
原始的 8,700 组预留数据仍未参与推理。

RTL 仿真包括：

- 124 组独立 Python Fraction 参照的定向/随机点积，含正负半格、饱和、最小负数、
  48 位累加溢出、不同右移量、最长 1,536 项点积、输入空拍及输出反压。
- 计算中途复位，确认未完成事务被丢弃。
- 16 组真实开发样本 × 42 个输出，共 **672 个点积**，同时比较 int48 累加值、int16 输出和饱和标志。
- 故意修改一个参考结果，确认自检报错；中途复位后重测，确认仍能完成。

16 组板级向量包括前 8 组开发样本和误差较大的 8 组，名单保存在报告中。
这属于硬件功能向量，不是独立模型精度测试。所有输入和期望结果均在下载时存入片内 ROM，
板上实际计算结果后比较；不会运行前序 attention/非线性层，也不会从原始 PSF 图像开始推理。

记录：[整数参考](../reports/integer_head_reference.json)、[RTL 仿真](../reports/integer_head_simulation.json)、
[仿真输出](../reports/integer_head_simulation.txt)、[构建及实板状态](../reports/integer_head_validation.md)。

## 复现

先完成 [量化参数准备](quantization.md)。从仓库根目录运行：

```powershell
$env:HF_HUB_OFFLINE='1'
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\prepare_integer_head.py --source F:\no-fft\test
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_head.py
New-Item -ItemType Directory -Force experiments\02_nofft_vit\build\vivado | Out-Null
Push-Location experiments\02_nofft_vit\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log integer_head_build.log -source ..\..\scripts\build_integer_head.tcl
    if ($LASTEXITCODE -ne 0) { throw 'Integer head build failed' }
} finally { Pop-Location }
```

构建脚本重建 `build/integer_head_hw/`；先关闭 GUI 中同名工程。
综合后逐项确认八个 `.mem` 文件被 Vivado 成功读取；缺少 ROM 初始化或发现未驱动信号即停止构建。
原始权重、数据及已有 DDR 程序保留。

## 下载与观察

Vivado Hardware Manager → Program Device，Debug probes 留空，选择：

```text
F:\GitHubProjects\fpga_ai_deployment\experiments\02_nofft_vit\build\integer_head_hw\acx720_v3_integer_head.bit
```

下载后按一下 S4 并松开，观察约 10 秒：

| 指示灯 | 正常完成后的状态 |
|---|---|
| LED0 | 常亮：672 个点积全部匹配 |
| LED1 | 持续闪烁：时钟心跳，周期约 0.67 秒 |
| LED2 | 熄灭：无比较错误或累加溢出 |

本次自检只需约几毫秒，可能看不到 LED0 从灭到亮的过程。
LED1 的含义与上一版 DDR 测试不同，这次通过后也会继续闪烁。
LED2 常亮代表失败，LED0 不亮则尚未通过；记录状态后再复位重试。
S4 会重新执行全部向量。当前没有串口输出，不要用上一实验的数字识别脚本检查本程序。

## 后续范围

本阶段通过后，将相同整数乘加/重定标扩展到更多 Linear/Conv 层，逐步连接 DDR 取数。
LayerNorm、Softmax、GELU、Sigmoid 等仍需定点参考及近似误差验证，之后才能串联完整网络。
