# 第四阶段：训练后量化的软件评估与参数导出

2026-11-25：完成 300 组校准、1,000 组开发验证的量化比较，导出候选 **W16A16_M125**。
这是量化/反量化（Q/DQ）软件仿真及整数参数准备；尚未实现整网整数推理，也没有生成新的 FPGA bitstream。

## 结果与选择

W 表示 Conv/Linear 权重位宽，A 表示其输入及 attention 矩阵乘法操作数位宽。
M125 表示对有符号激活的校准绝对最大值增加 25% 余量；softmax 概率保持固定 0～1 范围。
FP32 对标签的 39 位置 pooled RMSE 为 **0.1026544512**。下表区分模型本身误差与量化带来的额外偏差。

| 配置 | 对标签 RMSE | 相对 FP32 的 RMSE | 相对 FP32 最大单项偏差 | 激活截断次数 |
|---|---:|---:|---:|---:|
| W8_FP32 | 0.1025990212 | 0.0037768522 | 0.17593458 | 0 |
| W8A8 | 0.1048051556 | 0.0441583183 | 0.85423934 | 1,306 |
| W8A12 | 0.1026381550 | 0.0041074394 | 0.23938119 | 1,397 |
| W8A16 | 0.1025913421 | 0.0037971202 | 0.17575460 | 1,393 |
| W16A16 | 0.1026449117 | 0.0003209106 | 0.04928091 | 1,418 |
| W16A16_M125 | 0.1026576727 | 0.0000859917 | 0.00328008 | 1 |
| W16A16_M200 | 0.1026542570 | 0.0001409716 | 0.00727534 | 0 |

每个激活量化方案在这 1,000 组样本中统计了 2,575,404,000 个量化点值。W8_FP32 只量化权重，
不量化激活和偏置，因此其截断次数为 0 不能与其他方案按相同含义解读。
误差掩膜排除输出扁平索引 36、37、38；所有 42 个输出的最大偏差也保存在 JSON 中。

选择理由：直接 W8A8 的少量输出偏差很大，权重升至 16 位后改善明显；
原始 min/max 范围仍会截断开发样本，增加余量后改善。余量放大至 2 倍虽消除了本批截断，
但量化步长也变大，最大输出偏差反而高于 1.25 倍。因此以三个 W16A16 方案中开发集最大偏差最小者作为候选。
该选择使用了开发集，不能把本组结果当成未经调参的最终测试结果。

候选 W16A16_M125：相对 FP32 额外 RMSE **0.0000859917**，最大单项偏差 **0.00328008**；
对标签的 RMSE 为 **0.1026576727**，相比 FP32 增加约 **0.00314%**。
仍有 **1 个**激活量化值被截断，不能写成“零截断”。本批数据范围不保证覆盖未来输入。
用户尚未指定允许误差，系数物理单位尚未确认，所以这里只推荐进入下一步实现的候选，不宣称最终精度验收通过。

## 实际量化范围

- 覆盖 **58 个 Conv2d/Linear 层**的权重，按输出通道分别确定尺度。
- 量化上述层输入，以及 12 个 attention 的缩放后 Q、K、V 和 softmax 概率，共 **106 个观察点**。
- 有符号量化使用 `[-32767,32767]`，零点为 0；softmax 概率使用 `[0,65535]`，尺度为 `1/65535`。
- 每个权重通道尺度为 `max(abs(weight))/32767`；全零通道使用尺度 1。
- 有符号激活尺度为 `1.25 * max(abs(calibration_min),abs(calibration_max))/32767`。
- 就近舍入，正好半格时取偶数，然后饱和截断。权重和激活在 FP32 中计算量化码；接近半格处会受浮点表示影响。
- 偏置转换为 `round(bias/(input_scale*weight_scale))`，以 int64 保存；偏置计算和尺度乘积使用 FP64，反量化偏置再转 FP32。
  `format.json` 的 rounding 字段描述权重/激活量化；偏置规则以本条和 `quantization_core.py` 为准。

**仍保留浮点的部分**：本仿真的 MAC 累加及反量化、BatchNorm、LayerNorm、Softmax、GELU、Sigmoid、
HSwish、池化、残差加法、CA/CBAM 逐元素乘法，以及位置/class token 加法。
中间结果也未全部存成整数，W16A16 不表示所有网络张量都已改成 16 位。
后续还需确定整数累加、定点重定标、溢出/饱和和非线性近似；这些变化要再次与本次参考比较。

## 导出文件和位宽检查

候选目录：`build/quantization/W16A16_M125/`。

| 文件 | 用途 |
|---|---|
| `weights.bin` | 小端有符号 int16，C 顺序，58 层连续排列，无填充 |
| `quantized_tensors.npz` | 整数权重、通道尺度、int64 偏置及偏置尺度 |
| `remaining_state.npz` | 尚未整数化的参数/缓冲区，包含浮点归一化参数、位置编码等 |
| `format.json` | 每层权重形状、字节偏移、激活尺度和保守累加范围 |

Linear 权重形状 `[out,in]`，Conv2d 权重形状 `[out,in,kh,kw]`，尺度轴均为 0。
整数权重共 **21,821,604 个**、**43,643,208 字节（41.6214 MiB）**。
此大小只计算 weights.bin，不包含偏置、尺度、剩余状态、中间激活和程序工作区。
它小于已测试的 256 MiB DDR 容量，但不能据此认定整网时序、资源或吞吐率已经满足。

独立检查确认二进制与 NPZ 每个权重整数一致，偏置尺度关系正确，文件哈希一致。
Conv/Linear 的保守累加范围最大需要 **42 位有符号数**；attention 的 QK 和概率×V 分别需要 37、38 位。
后续可先按 48 位累加器设计，**不能统一使用 int32 累加**。该范围计算不等于已完成整数 RTL 验证。

完整导出包重新加载时使用保存的整数权重、剩余状态和激活尺度；全部 1,000 组预测与导出前逐位一致。
这证明本次软件格式可重载，不证明未来 FPGA 结果与浮点仿真逐位一致。

## 数据与复现

只使用固定校准/开发划分；8,700 组预留验收数据未用于本轮推理或选方案。
原始权重、用户数据、第一阶段/全容量 DDR bitstream 均保持不变。
详细量化文件放在 Git 忽略的 build/；提交脚本、说明和小型结果报告即可。

先完成 [软件参考准备](software_reference.md)，然后从仓库根目录运行：

```powershell
$env:HF_HUB_OFFLINE='1'
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\tests\test_quantization.py
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\run_quantization.py --source F:\no-fft\test
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\verify_quantized_export.py
```

六项单元测试检查取整/饱和、零通道、unsigned 概率、整数点积参照、范围余量和导出状态覆盖。
全数据流程先检查 attention 适配器不量化时与 FP32 基线一致，再校准、比较七种方案、选择候选、导出并重载验证。
未使用 QAT、未改动训练权重源文件。CPU 软件运行时间不用于预测 FPGA 吞吐率。

结果：[方案比较](../reports/quantization_results.json)、[校准范围](../reports/quantization_calibration.json)、
[二进制与累加范围核验](../reports/quantization_export_verification.json)。

方法参考：[PyTorch 的校准与通道量化说明](https://pytorch.org/blog/quantization-in-practice/)、
[量化/反量化接口定义](https://docs.pytorch.org/docs/main/generated/torch.fake_quantize_per_channel_affine.html)。
本仓库使用显式实现以支持 12/16 位和 attention 操作数，实际规则以源码和导出格式为准。

## 下一步

先用导出的 W16A16_M125 参数实现整数乘加、偏置与重定标的逐算子参考；
再处理 LayerNorm、Softmax、GELU/Sigmoid 等非线性算子，确定完整定点图后进行单层和整网实板对照。

后续进展：[末层整数乘加、重定标及上板自检](integer_head.md)，已生成可下载的单层测试文件。
