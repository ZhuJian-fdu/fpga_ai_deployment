# 第三阶段：数据划分与 FP32 软件参考

2026-11-25：DDR 两轮全容量比较已通过用户实板观察；本阶段在电脑运行原始模型，
建立未来量化和 RTL 对照的基准。此时 FPGA 仍运行 DDR 测试，没有运行该神经网络。

## 数据来源与固定划分

用户确认 `F:/no-fft/test` 的 10,000 个样本完全独立，未用于训练或选择最佳模型。
该来源信息按用户确认记录，未独立验证训练历史。原归档脚本曾复用相同的验证/测试路径名称，
不能仅凭目录名称判断这次提供的数据批次；历史评估与本次数据的来源记录分别保存。

全部文件已逐个检查并计算哈希：输入 `[5,112,112]` float64，标签 `[7,30]` float32，
输入各通道范围 0～1，没有非有限数，转为 float32 后没有完全重复的输入。
本次不做额外归一化，只转换为 float32。原始五幅 PSF 的顺序和预处理生成规则仍待补充。
检查不等于已经排除近重复或同场景样本关联；若有分组信息，后续应据此复核划分。

按输入内容哈希确定排序，固定三组互不重叠的文件：

| 用途 | 数量 | 使用规则 |
|---|---:|---|
| 量化校准 | 300 | 后续估计激活范围；使用后不计入独立测试 |
| 开发验证 | 1,000 | 比较 FP32 与不同量化方案、定位误差 |
| 预留验收 | 8,700 | 当前仅做文件/数值完整性检查，尚未推理；方案冻结后才用于验收 |

原始文件未修改或移动。详细文件清单和每个文件哈希保存于忽略目录 `build/dataset/manifest.json`，
Git 留档保留 [数据检查摘要](../reports/dataset_audit.json)、划分算法及清单哈希。
换电脑后使用同样输入内容和参数可重建同样的分组；清单中的本机源路径随机器变化。

## 本次软件参考结果

- 从核验过的归档中提取两个模型源文件及权重；源码不改写，权重用 `weights_only=True` 加载，
  `load_state_dict(strict=True)` 成功，参数量 21,902,619，实际 patch 为 16。
- `eval()` 模式，不训练、不下载额外预训练权重。关闭融合 attention，保留显式算子便于后续逐层对照。
- 使用 Python 3.11.1、PyTorch 2.7.1+cpu、timm 1.0.15、NumPy 1.26.4。
  这是本次部署参考环境，原训练环境版本尚未提供，不声称与原环境逐位相同。
- 1,000 个开发验证样本输出均为有限的 42 维向量。
- 39 个有效输出位置的 pooled RMSE 为 **0.1026544512**，MAE 为 **0.0462693842**。
  排除扁平索引 36、37、38，使用标签前六列；这些是相对标签的模型误差，不是量化误差。
- 第一个样本单独推理与 batch=8 推理最大差异 **2.2352e-7**，通过诊断阈值 `rtol=1e-5, atol=1e-6`。
  此阈值用于软件一致性检查，不是最终 FPGA 允许误差。

本指标不做 full-210 补零/piston 处理，也不计算波前误差，因此不能直接与原归档的
full-210 RMSE 或波前 RMSE 比较。系数物理单位仍未确认，不把该数值解释为某个物理精度。

完整记录见 [FP32 参考报告](../reports/fp32_reference.json)。预测、标签、掩膜及样本顺序保存于
`build/reference/development_fp32.npz`，文件哈希已记入报告，供后续量化与硬件对照。

## 复现

在仓库根目录运行。使用实验 02 的独立 Python 环境，不修改实验 01 环境：

```powershell
py -3.11 -m venv experiments\02_nofft_vit\build\.venv
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe -m pip install --upgrade pip==25.3
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe -m pip install -r experiments\02_nofft_vit\requirements-reference-cpu.txt
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\audit_dataset.py --source F:\no-fft\test --independent-confirmed
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\prepare_model.py --archive F:\no-fft\no-fft.tar.gz
$env:HF_HUB_OFFLINE='1'
$env:HF_HUB_DISABLE_TELEMETRY='1'
.\experiments\02_nofft_vit\build\.venv\Scripts\python.exe experiments\02_nofft_vit\scripts\reference_fp32.py --source F:\no-fft\test
```

`--independent-confirmed` 仅在数据所有者确认未参与训练或选模时使用；换数据时不要机械沿用。
准备脚本会拒绝哈希不同的新模型归档，需先复核新源码和权重再更新来源记录。
依赖版本组合参考 [PyTorch 官方安装表](https://pytorch.org/get-started/previous-versions/)，
`pretrained=False` 的创建接口见 [timm 官方文档](https://huggingface.co/docs/timm/reference/models)。

## 下一阶段

先使用校准组统计激活范围，逐层比较权重/激活不同位宽带来的额外误差。
对 Softmax、LayerNorm、GELU、Sigmoid 等算子单独建立近似或定点参考，
选择数值方案后再实现可复用乘加单元和单层实板对照。
后续进展已记录于 [首轮量化比较与参数导出](quantization.md)；尚未完成最终量化精度验收或整网上板。
