# FPGA AI Deployment 学习仓库

从一个可验证的小模型开始，逐步学习 AI 模型训练、整数化、RTL 实现和 FPGA 部署。

## 实验索引

| 编号 | 实验 | 目标芯片 | 当前边界 |
|---|---|---|---|
| 01 | [8×8 手写数字线性分类器](experiments/01_digits_linear/README.md) | ACX720-V3 / XC7A35T-FGG484-2 | 已完成实板推理：4500 个分数一致，准确率 433/450（96.22%） |
| 02 | [no-FFT PSF 系数回归：CA + CBAM + ViT](experiments/02_nofft_vit/README.md) | ACX720-V3 / XC7A35T-FGG484-2 | 教学阶段已结束：两层全连接+GELU 实板 1,000 组通过；整网未部署，待以后换板另开实验 |

实验 02 已于 2026-11-25 按用户决定结束当前板卡上的模型部署，见 [结束与换板交接](experiments/02_nofft_vit/docs/project_closeout.md)。

## 目录约定

- `experiments/NN_name/`：每个实验独立保存说明、软件、硬件、脚本和验证记录。
- 实验内 `board/`：具体板卡信息和引脚约束；芯片型号不能代替开发板型号。
- 实验内 `reports/`：适合 Git 留档的小型结果、工具版本和阶段结论。
- 实验内 `baseline/`：已实测模型的小型快照，用于恢复历史实验。
- 实验内 `build/`：自动生成的模型、仿真、Vivado 工程与报告，不提交。
- 根目录 `.venv/`：本机 Python 环境，不提交。

新增模型或板子时增加实验编号，并在本表登记；已有实验保留可复现入口。
共享模块等实际有复用需求后再提取，避免初学阶段建立复杂框架。

## 开始学习

打开 [实验 01](experiments/01_digits_linear/README.md)，按其步骤操作。
上传与克隆后恢复请看 [GitHub 留档指南](docs/github_archive.md)。
实验 01 的历史版本已归档至 [GitHub](https://github.com/ZhuJian-fdu/fpga_ai_deployment)。
实验 01 于 2026-11-25 从远程重新克隆并通过模型恢复与四项仿真，见 [远程归档检查](experiments/01_digits_linear/reports/github_validation.md)。
实验 02 的本次收尾已在本地整理；本次未执行 commit 或 push。
后续提交前检查 `.gitignore`，不提交工具安装包、
完整第三方资料、私有文件或大体积生成物。第三方板卡资料优先记录官方链接。
