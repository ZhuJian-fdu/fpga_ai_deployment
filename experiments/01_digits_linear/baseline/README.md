# 2026-11-24 实板模型快照

这里保留本实验训练得到、实际在 ACX720-V3 上验收的模型，而非第三方预训练模型。
`model.npz` 保存整数/浮点参数、缩放系数及训练/测试样本索引；
`weights.mem` 和 `biases.mem` 是综合使用的权重初始化文件，三者共约 17 KiB。
不包含完整数据集、厂商资料或 Vivado 二进制程序。

三个文件的原始字节 SHA-256 对应 [构建清单](../reports/ai_build_manifest.json)
中的 `build/model/` 条目。`.mem` 保留原始 CRLF，Git 不转换这些快照的换行。

从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\restore_baseline.py
```

脚本先校验快照、测试集索引和全部 450 张图的存档分数，再将模型恢复到
`build/model/` 并生成仿真输入；这会覆盖该目录中的同名模型和向量文件。
不会连接或下载到板卡。随后按 [AI 教程](../docs/ai_bringup.md) 仿真和构建。

学习训练过程仍使用 `software/train_export.py`。不同环境重新训练的浮点结果可能存在差异；
保留这份快照便于准确恢复历史实验，后续模型应建立新的实验目录或新的明确版本。
