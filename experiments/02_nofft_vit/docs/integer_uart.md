# 末层整数推理：串口实时输入和结果回读

固定向量自检已由用户观察 LED 确认通过，见
[实板观察记录](../reports/integer_head_hardware_observation.json)。
本步骤把输入改为电脑实时发送，并把实际计算结果送回电脑逐项比较。
**仍然只部署 `head.7`（96 → 42），不是整个 ViT 模型；此版本不使用 DDR。**
前面各层在电脑上运行，生成 1,000 组开发集隐藏向量；8,700 组预留验收数据未使用。

## 数据路径

电脑发送 96 个 INT16 → FPGA 输入 RAM → 固定权重逐输出点积 →
48 位累加 → 整数乘数/移位、最近偶数舍入、INT16 饱和 → 串口返回。
电脑核对每个输出的累加值、量化值、饱和及溢出标志，共 42,000 个输出记录。
板上没有预期结果 ROM，也不在板上比较答案。

## 下载和检查

Vivado Hardware Manager → Program Device，选择：

```text
experiments/02_nofft_vit/build/integer_uart_hw/acx720_v3_integer_uart.bit
```

Debug probes 留空。下载后按 S4 并松开，保持 UART USB 连接电脑。
**等待电脑发送时：LED0 熄灭、LED1 闪烁、LED2 熄灭。**
成功完成一组请求后 LED0 亮；下一组请求开始时它会熄灭，最后一组完成后保持亮。
LED2 表示曾发生接收错误、超时、CRC 错误或运算溢出，直到 S4 复位才清除。

关闭占用串口的串口助手。从仓库根目录运行（把 COM10 换成实际 UART 端口）：

```powershell
.\.venv\Scripts\python.exe experiments\02_nofft_vit\software\check_integer_head_board.py --port COM10 --limit 1000
```

脚本每 100 组显示进度，遇到错误停止，并写入
`reports/integer_head_uart_hardware.json`。只有 `passed: true` 且
`checked_samples: 1000` 才表示本次 1,000 组回读通过。
按请求和响应字节数计算，115200 波特率下仅传输就至少需要约 51 秒；实际还包括软件开销。
LED 状态不能替代整数结果回读，且串口测试通过也不代表完整网络已上板。

## 串口协议

115200，8N1；50 MHz 时钟，434 个周期/位。每次只发一个请求，收到完整响应后再发下一组。
所有多字节整数均为小端；有符号数使用二进制补码。
CRC-16/CCITT-FALSE：多项式 0x1021、初值 0xFFFF、不反射、不做末尾异或。
CRC 覆盖帧头之后、CRC 之前的所有字节，CRC 自身按小端发送。

| 方向 | 内容 | 字节数 |
|---|---|---:|
| 请求 | A5 5A + 序号 uint16 + 96 × int16 + CRC uint16 | 198 |
| 响应 | 5A A5 + 序号 uint16 + 状态 uint8 + 42 × 记录 + CRC uint16 | 385 |
| 输出记录 | 累加值 int48 + 量化值 int16 + 标志 uint8 | 9 |

状态 0 为成功，1 为请求 CRC 错误（记录全零且不启动运算），2 为运算错误。
记录标志 bit0 为饱和，bit1 为运算错误，其余为零。
正常饱和不等于运算错误，必须与参考值一起核对。
收到部分帧后若连续约 100 ms 没有新字节，丢弃该帧并置错误灯，不发送响应。
串口停止位错误也丢弃正在接收的帧。计算和发送期间不接收下一请求。

## 复现与归档

先按 [整数末层说明](integer_head.md) 生成参考数组和系数，再执行：

```powershell
.\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\test_integer_uart.py
& F:\Xilinx\Vivado\2023.2\bin\vivado.bat -mode batch -source experiments\02_nofft_vit\scripts\build_integer_uart.tcl -log experiments\02_nofft_vit\build\integer_uart_build.log -journal experiments\02_nofft_vit\build\integer_uart_build.jou
```

仿真需要 PATH 中有 Icarus Verilog 的 `iverilog` 和 `vvp`。
此实验复用 `experiments/01_digits_linear/rtl/uart_rx.v` 和 `uart_tx.v`，因此复现时保留整个仓库。
构建脚本检查四个系数 ROM 的初始化日志、布局布线后时序和阻断级 DRC。
测试报告和源代码归档到 Git，`build/` 中的参考数组、Vivado 工程和 bit 文件不提交。
构建及仿真通过与实板回读通过分别记录，见 [验证记录](../reports/integer_uart_validation.md)。
