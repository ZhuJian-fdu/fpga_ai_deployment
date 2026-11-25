# GitHub 远程归档检查

检查日期：2026-11-25（Asia/Shanghai）。
仓库：[ZhuJian-fdu/fpga_ai_deployment](https://github.com/ZhuJian-fdu/fpga_ai_deployment)。
本次检查提交：[8df0584](https://github.com/ZhuJian-fdu/fpga_ai_deployment/commit/8df058486633e0f6d9e95ac47ae48965b6c09be8)。

## 检查结果

- GitHub 页面可访问，远程 `main` 与本地当时 HEAD 完全相同。
- 重新从 GitHub 克隆，确认有 62 个已跟踪文件；未包含 `build/`、`.venv/` 或 `board/vendor/`。
- Markdown 本地文件链接、JSON 解析和提交空白检查通过。
- 在新克隆中运行 `restore_baseline.py`，三个模型快照的 SHA-256 与历史构建清单一致。
- 恢复模型重新计算的全部 450 张图像分数、样本索引及标签，与实板存档一致。
- 分类核心仿真：454 张图，4540 个整数分数一致，含复位中止检查。
- 协议仿真：456 个合法响应帧通过，错误 CRC、像素、长度、超时和接收错误的处理与恢复通过。
- UART 完整链路仿真：10 张图，460 个响应字节一致。
- AI 顶层复位仿真通过。

结论：该远程提交具备恢复本实验模型、运行已验证仿真及重建板级工程所需的源文件。
仿真沿用本机已安装的 Python 3.11 依赖和 Icarus；本次没有在另一操作系统安装工具、
重新执行 Vivado 构建或重新进行实板测试。Vivado 和硬件结果仍引用 2026-11-24 的实测记录。

发现 README 和首次上传指南仍有上传前的状态描述，已在本次检查后的文档修改中更正；
这些更正不属于上方被检查的首次提交。仓库介绍、标签和 LICENSE 尚可按后续用途补充，
不影响本次归档与模型恢复结果。
