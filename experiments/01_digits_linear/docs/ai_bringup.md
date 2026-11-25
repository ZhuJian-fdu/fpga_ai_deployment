# 第三课：在 ACX720-V3 上识别手写数字

2026-11-24 实测已通过：450 张测试图的 4500 个分数与 Python 参考完全一致，准确率 96.22%。以下步骤供复现，结果见 [验证记录](../reports/ai_validation.md)。

前置条件已完成：点灯成功、COM11 串口回环两轮通过，用户确认 LED0 闪烁、LED1 常亮、LED2 熄灭。
本课目标：PC 发送图片，FPGA 独立完成 640 次整数乘加，再把类别和分数返回 PC。
电脑只负责发送输入、解析输出和核对，不替 FPGA 计算返回值。

## 1. 下载 AI 程序

保持已成功的供电、下载及 UART 接线。在 Vivado Hardware Manager 中，
右键 `xc7a35t` → Program Device，选择：

```text
F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/build/ai/acx720_v3_ai.bit
```

Debug probes 留空。下载后按一下 S4，开始测试后不要按复位。
刚按完 S4、尚未发送图片时，应看到 LED0 闪烁，LED1 和 LED2 都熄灭。
这会替换当前 FPGA 的串口回环电路；此时不能再用原样回传脚本测试。

| LED | AI 程序中的含义 |
|---|---|
| LED0 | 每半秒翻转，时钟心跳 |
| LED1 | 完成第一幅图的推理后常亮，S4 清除 |
| LED2 | UART 或协议发生过错误后常亮，S4 清除 |

## 2. 先识别 10 张图

关闭占用 COM11 的串口助手，在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\software\infer_board.py --port COM11 --count 10
```

每行包含真实标签 `label`、FPGA 预测、Python 参考预测，以及 `scores=MATCH`。
所有分数一致时显示 `PASS`。首张图的真实标签为 1，基线模型预测为 8；
如果 FPGA 也得到同样的 10 个分数，就是硬件正确复现了模型的一次误判。

请区分两件事：

- 硬件实现正确：FPGA 的每个分数和 Python 整数参考完全一致。
- 模型识别正确：预测数字与真实标签相同。小线性模型并不保证每张图都识别正确。

测试通过后，LED1 应常亮、LED2 应熄灭。输出保存为 `build/board_inference_10.json`。

## 3. 验收完整测试集

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\software\infer_board.py --port COM11 --count 450
```

验收条件：450 张测试图的 4500 个分数全部一致，预测与整数参考一致。
当前模型对应 433/450 张识别正确，即约 96.22%。不能只看准确率：分数不一致但恰好类别相同也算验证失败。

报告保存为 `build/board_inference_450.json`。完成实测后将小型指标和结论整理入 `reports/`。
报告中的 `roundtrip_ms` 包含 PC、USB、UART 和运算等待，不等于 FPGA 单次计算延迟。

## 4. 程序内部发生了什么

1. PC 从固定测试集取一幅 8×8 图，按行展开为 64 个数。
2. PC 发送帧头、序号、长度、像素和 CRC。
3. FPGA 收满并校验后，才启动分类器。
4. 分类器依次累加 10 个类别分数，选最大值。
5. FPGA 返回类别、10 个分数及 CRC；PC 检查所有字段。

完整字段约定见 [图像协议](image_protocol.md)。权重随 bitstream 装入存储器，
板上没有 Python、scikit-learn 或训练过程。

## 5. 从源码重新构建

首次克隆先按实验 README 安装环境，执行 `scripts/restore_baseline.py` 恢复本次实板模型；
若要重新学习训练流程，也可执行 `software/train_export.py`。
重新训练或重新导出权重后，必须重新构建并下载 AI bitstream；不能只更新电脑参考模型。

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py protocol
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py ai_uart
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py ai_reset
New-Item -ItemType Directory -Force experiments\01_digits_linear\build\vivado | Out-Null
Push-Location experiments\01_digits_linear\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -log ai_build.log -source ..\..\scripts\build_ai.tcl
    if ($LASTEXITCODE -ne 0) { throw 'AI build failed' }
} finally { Pop-Location }
```

Vivado 图形界面工程为 `build/ai/acx720_v3_ai.xpr`。若不存在，在 Tcl Console 中执行
`source F:/GitHubProjects/fpga_ai_deployment/experiments/01_digits_linear/scripts/create_ai_project.tcl`。
脚本会把 `weights.mem` 与 `biases.mem` 加入项目，综合时用于初始化模型存储。
GUI Generate Bitstream 输出在 `acx720_v3_ai.runs/impl_1/acx720_v3_ai_top.bit`，
修改代码后请使用本轮生成的文件；脚本固定输出另在 `build/ai/acx720_v3_ai.bit`。

如果响应帧格式错误，先确认下载的是 AI bitstream，而非 UART 回环程序。
如果分数不一致，保留完整错误输出，检查 PC 模型是否与构建时一致。
只有真实板卡的完整测试集比较通过，才将 AI 部署记为完成。
