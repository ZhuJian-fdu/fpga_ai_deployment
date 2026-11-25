# 两层全连接与 GELU 在 FPGA 上串联

上一阶段仅将最后的 `head.7` 放到板上，已完成 1,000 组、42,000 个输出记录的实板回读。
本阶段扩展为：**192 个输入 → head.4（192→96）→ GELU → head.7（96→42）→ 42 个输出**。
中间的 Dropout 在推理模式下不改变数据。前面的网络仍在电脑上执行，本版本不连接 DDR。

## 本步学习什么

乘加处理线性层；GELU 是非线性函数，不能用另一组固定权重代替。
这里预先计算每个 INT16 输入对应的 GELU 输出，烧入片上 ROM。
FPGA 计算出前一层结果后，读表得到 GELU 结果，写入下一层输入 RAM，然后执行最后一层。
主机只发送 192 个输入，中间 96 个值不经过电脑。

新 RTL 使用可配置输入/输出长度的 `integer_dense_engine.v`，两层分别实例化该模块，
各自复用已经验证的 `int16_dot_requant.v`。当前两套乘加硬件独立，按层顺序运行，尚未做跨层硬件复用优化。

## 整数和查表的含义

每个通道执行 `acc = bias_int + Σ(input_int × weight_int)`，使用 48 位有符号累加器。
再用整数乘数与右移转换尺度，采用最近偶数舍入，输出限制在 [-32767,32767]。

GELU 表中每项定义为：

```text
x = signed_int16(address) × pre_gelu_scale
gelu(x) = 0.5 × x × (1 + erf(x / sqrt(2)))
table[address] = clamp(round_to_even(gelu(x) / gelu_output_scale), -32767, 32767)
```

表覆盖全部 65,536 个 INT16 位模式，按无符号地址读取对应有符号输入，包括负数。
没有插值或截断查表区间。使用 Python math.erf 生成的表与 PyTorch float64 GELU 的量化结果
逐项比较，65,536 项全部一致。

| 尺度 | 数值 |
|---|---:|
| 192 维输入 | 0.0000341448896619 |
| GELU 前输入 | 0.0000345842504020 |
| GELU 后/末层输入 | 0.0000192794704268 |
| 42 维最终输出 | 0.0000221813996034 |

新引入的 GELU 前尺度只由既定 300 组校准数据确定，并留 25% 余量。
其他尺度沿用已选定的 W16A16_M125 方案和末层输出尺度。
全表中有 9,601 个地址因 GELU 输出超出 INT16 表示范围而饱和，属于上述量化定义；
1,000 组开发数据实际访问的地址没有饱和。相对截幅后的连续函数，表项最大绝对误差为 0.00000963967。
全地址空间相对未截幅函数的最大误差为 0.355804，不能把这个数误解为开发样本上的误差。

1,000 组开发数据中，两层重定标和 GELU 均无饱和。整数乘数/移位的结果与原比例的
独立精确分数计算逐项相同；两层实际累加值都可能超出有符号 32 位，因此继续采用 48 位。

## 软件误差和当前验证范围

有效 39 个输出位置上的软件结果：

| 对照 | RMSE |
|---|---:|
| 相对原 Q/DQ 候选模型 | 0.0000123033 |
| 相对上一版仅末层整数模型 | 0.0000137522 |
| 相对 FP32 模型 | 0.0000864291 |
| 相对标签 | 0.1026577965 |

相对 Q/DQ 候选的全部 42 维最大绝对差为 0.0000626644。
这些是开发数据上的比较，不是预留集的最终验收；8,700 组预留数据未使用。
详细数值和文件哈希见 [整数参考报告](../reports/integer_tail_reference.json)。
本阶段已于 2026-11-25 通过 COM10 完成 1,000 组实板回读，42,000 个最终输出记录逐项一致。
实现与实板状态见 [验证记录](../reports/integer_tail_validation.md)。

## 下载与复现实板回读

Vivado Program Device 选择：

```text
experiments/02_nofft_vit/build/integer_tail_hw/acx720_v3_integer_tail.bit
```

Debug probes 留空。下载后按 S4 并松开，保持 UART USB 连接。
等待输入时应为 **LED0 熄灭、LED1 闪烁、LED2 熄灭**。
每组完成后 LED0 亮；下一组开始时清除。LED2 为错误锁存，需 S4 清除。

从仓库根目录运行，端口按实际识别结果填写；最近一次识别为 COM10：

```powershell
.\.venv\Scripts\python.exe experiments\02_nofft_vit\software\check_integer_tail_board.py --port COM10 --limit 1000
```

返回的 42 个最终输出记录都包含末层 48 位累加值、INT16 结果及状态标志。
主机逐项比较，并保存 `reports/integer_tail_uart_hardware.json`；中间结果在 RTL 仿真中单独核对，
本串口协议不返回中间 96 维数据。总耗时包含主机和串口开销，不能当作 FPGA 纯计算时间。

协议为 115200、8N1、所有整数小端；CRC 定义沿用 [上一阶段](integer_uart.md)。
本版本请求为 `C3 3C + 序号uint16 + 192×int16 + CRCuint16`，共 390 字节；
响应为 `3C C3 + 序号uint16 + 状态uint8 + 42×9字节记录 + CRCuint16`，共 385 字节。
帧头区别于上一版，避免两版程序误用。仍然每次只允许一个未完成请求。
状态 1 为请求 CRC 错误，状态 2 为计算错误。记录 bit0 为末层输出饱和，bit1 为计算错误。
前层重定标饱和或前层溢出也传播为计算错误；GELU 表内的量化饱和不单独返回标志。

## 复现与后续存储优化

先完成前述量化及末层参考生成，再从仓库根目录运行：

```powershell
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\prepare_integer_tail.py --source F:\no-fft\test
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_tail.py
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_tail_uart.py
& F:\Xilinx\Vivado\2023.2\bin\vivado.bat -mode batch -source experiments\02_nofft_vit\scripts\build_integer_tail.tcl -log experiments\02_nofft_vit\build\integer_tail_build.log -journal experiments\02_nofft_vit\build\integer_tail_build.jou
```

UART 收发器继续复用实验 01 的源码。所有中间文件放在新的 `build/integer_tail/` 和
`build/integer_tail_hw/`；上一阶段 bit、参考和实板记录保留。
源码、教程、小型报告纳入 Git；模型、数据、MEM、Vivado 工程及 bit 位于忽略的 `build/`。

完整查表优先保证本阶段的数值可核对性，但本版用满 50 个 BRAM Tile，无法直接继续往片上 ROM 堆放更多层。
后续需要压缩 GELU 表并重新验证误差，或调整存储实现，再结合 DDR 缓冲和可复用乘加单元扩展网络。
