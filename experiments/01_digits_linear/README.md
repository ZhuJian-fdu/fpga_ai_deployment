# 实验 01：在 Artix-7 上部署最小手写数字分类器

目标：输入一幅 8×8 灰度数字图像，在 FPGA 中完成整数推理，返回数字 0～9。
本实验用电脑提供图像，通过 UART 发送给板卡；摄像头属于后续独立实验。

**当前状态：已完成 ACX720-V3（35T）上的最小模型部署与正常图像实板推理验收。**
2026-11-24 经 COM11 先测试 10 张、再测试全部 450 张图像，4500 个整数分数及预测类别均与 Python 参考一致，准确率 433/450（96.22%）。
完整 AI 工程已通过仿真、布局布线、时序和 DRC 检查；实测详情见 [AI 验证记录](reports/ai_validation.md)。
复现步骤见 [AI 上板教程](docs/ai_bringup.md)。
串口过程可按 [UART 回环教程](docs/uart_loopback.md) 重现。
点灯工程保留在 [点灯教程](docs/acx720_bringup.md)，方便重现。
已准备软件训练、整数模型、RTL 仿真、独立综合与点灯模块。
实际验证记录见 [reports/validation.md](reports/validation.md)。

## 你将学会什么

训练发生在电脑上；FPGA 负责推理。训练产出的权重被转成整数并放入 FPGA 的存储器，
Verilog 描述乘法器、加法器、寄存器以及控制它们工作的状态机。
Vivado 把这些描述综合、布局布线，生成配置 FPGA 电路的 `.bit` 文件。
不是把 Python 文件直接复制到板子上执行。

本实验用多分类逻辑回归，即 **64 个输入、10 个输出的单层线性分类器**。
它是训练出来的机器学习模型，没有隐藏层，也不是 CNN。
先掌握这条部署链路，再增加隐藏层、激活函数和卷积。

```text
电脑：数据集 → 训练浮点模型 → 整数化 → 导出权重和测试向量
                                      ↓
仿真：同一幅图像 → Verilog 推理 → 逐分数对比 Python 整数结果
                                      ↓
板卡：电脑图像 → UART → 像素存储 → 乘加运算 → 取最大分数 → UART 返回
```

数据采用 scikit-learn 自带的 `load_digits`：1797 张 8×8 图像、像素值 0～16。
这不是 28×28 的 MNIST；不要混用这两种输入格式。
数据出处：[scikit-learn load_digits](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html)。

## 为什么适合这颗芯片

XC7A35T 有 33,280 个逻辑单元、90 个 DSP48E1、1,800 Kbit BRAM。
1,800 Kbit 约等于 225 KiB，不能当成 1,800 KB。
这些是芯片总资源，不代表全部都能用于模型。
来源：[AMD Artix-7 产品资源表](https://www.amd.com/en/products/adaptive-socs-and-fpgas/fpga/artix-7.html)。

本模型只需 640 个 int8 权重（640 字节）、10 个 int32 偏置（40 字节）和
64 字节像素。每幅图像做 640 次乘加，先复用一条乘法数据通路，便于观察时序。
实际 DSP、LUT 和存储资源以综合报告为准；字节数不能直接换算成综合后 BRAM 数量。
本阶段不需要外接 DDR 或在 FPGA 上运行操作系统。

## 文件在哪里

```text
01_digits_linear/
├── README.md                 # 按阶段学习入口
├── requirements.txt          # 固定 Python 依赖版本
├── board/README.md           # 已核验板卡资料，旁边保存顶层与 XDC
├── baseline/                # 已实测模型快照，可免训练恢复
├── docs/integer_model.md     # 软件与硬件共同遵守的数值规则
├── software/train_export.py  # 训练、量化、导出、评估
├── rtl/digit_classifier.sv   # 可综合的整数推理核心
├── rtl/heartbeat.v           # 参数化点灯模块
├── sim/                     # 自动核对结果的 testbench
├── scripts/                 # 仿真和 Vivado Tcl 入口
├── reports/                 # 小型验证记录，提交 Git
└── build/                   # 自动生成，不提交 Git
```

## 第 0 步：确认工具和开发板

本机检查发现：Vivado 2023.2 在 `F:\Xilinx\Vivado\2023.2`，Icarus Verilog 已在 PATH 中。
Vivado 已实际启动并识别 `xc7a35tfgg484-2`。
系统默认 `python` 是 3.8，因此本实验明确使用 Python 3.11 虚拟环境。

暂时沿用已安装的 Vivado。换电脑时，选择支持目标器件和操作系统的版本，并安装
Artix-7 器件支持与下载线驱动。2023.2 的器件支持可参考
[AMD UG973 支持器件表](https://docs.amd.com/r/2023.2-English/ug973-vivado-release-notes-install-license/Supported-Devices)。
2026.1 起授权机制已有变化，如以后升级，应查看当时的
[AMD 授权说明](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/licensing-faq.html)。

上板需要补齐 [board/README.md](board/README.md)：型号已确认是 ACX720-V3，
已核验 V3 原理图中的时钟、LED、复位、UART 和相应 I/O 电压配置。
该文件记录了资料来源、可调 VCCIO 的使用前提、已验证接线与尚未核实的细节。

**验收：**工具能识别器件，板卡连接与引脚有可靠资料可查。

## 第 1 步：先在电脑上识别一张图

以下命令均在仓库根目录的 PowerShell 执行。本机已创建 `.venv`；在新电脑首次运行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r experiments\01_digits_linear\requirements.txt
```

无需执行 `Activate.ps1`，直接调用虚拟环境内的解释器即可。
要准确恢复本次实板模型，可先运行 `scripts/restore_baseline.py`，见 [模型快照说明](baseline/README.md)。
下面用于学习重新训练；它会覆盖 `build/model/`，不会改动已归档快照。

训练和导出：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\software\train_export.py
```

输出会列出浮点准确率、整数准确率和两者预测一致率，并打印第一张测试图的字符预览。
观察三个问题：图像的真实数字是什么？整数模型识别成什么？量化后准确率改变了多少？

训练集占 75%，测试集占 25%，随机种子固定为 42，按类别分层。
模型只在训练集拟合，量化比例只由训练后的权重确定。
测试集用于最终评估；后续调超参数时应再从训练集中划出验证集，不反复按测试集调参。

输出在 `build/model/`，含 `metrics.json`、浮点/整数模型、权重和测试向量。
这些生成物可用脚本重建；如需保存某次实验，把小型指标和权重摘要收录到 `reports/`。

**验收：**能解释模型怎样从 64 个像素得到 10 个分数，整数模型准确率有明确记录。

## 第 2 步：核对 FPGA 要做的整数运算

阅读 [整数模型约定](docs/integer_model.md)，然后运行：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py classifier
```

testbench 会把测试图片送入 RTL，对每张图的全部 10 个分数逐一核对，
最后核对预测类别；另有 4 张合成图验证算术边界，以及运算中复位检查。
通过时显示 `PASS`。仿真一致不等于识别全对：RTL 应当复现整数模型，包括模型自己的误判。

先看懂接口：空闲时写满 64 个像素，随后让 `start` 高一个时钟；
`busy` 为高时等待，`done` 高一个周期表示结果有效。
后续 UART 模块只负责按照这个协议送图和取结果。

**验收：**所有测试向量的所有整数分数完全一致，无超时。

## 第 3 步：先把板卡点亮

点灯的作用是确认电源、下载器、时钟、复位、引脚约束和工具链都能工作。
已提供可仿真的计数模块：

```powershell
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py heartbeat
```

板卡资料已确认，以下前三项已由脚本准备；操作详情见上方点灯教程：

1. 添加板级 `top`：接入真实时钟，处理复位同步和 LED 有效电平。
2. 填写 `pins.xdc`：`PACKAGE_PIN`、`IOSTANDARD` 和实际时钟周期。
3. 创建 Vivado 工程，器件选择 `xc7a35tfgg484-2`，综合并实现。
4. 检查 DRC 与时序结果，再生成 bitstream。
5. 按板卡手册供电和连接 JTAG，在 Hardware Manager 识别器件。
6. Program Device 下载 `.bit`，观察 LED 每半秒翻转一次。

`heartbeat.v` 的 50 MHz 默认值只是示例，必须按真实板卡时钟修改。
现在分别有点灯、UART 回环和完整 AI 三套顶层与约束，保留各阶段工程以便复现。

**验收：**实物 LED 周期正确；记录板卡版本、工具版本、约束来源及验证日期。

## 第 4 步：建立电脑与板卡的图像通道

点灯通过后实现 UART 回环，再定义带帧头、长度、校验和超时的图像协议。
电脑发送 64 个像素，FPGA 收满一帧后才启动推理，再发送预测结果。
串口波特率、时钟分频和电平按真实板卡确定。

UART 收发、16 字节 FIFO 回环和 PC 自动核对脚本已实现；COM11 上连续两轮、合计 2592 字节实物比较通过。
ACX720-V3 已有板载 CH340E，连接其 UART USB 接口即可使用。图像帧协议已实现并通过仿真，见 [协议说明](docs/image_protocol.md)。

**验收：**连续多次收发数据完全一致，错误指示灯熄灭；图像协议另需验证错误帧处理与恢复。

## 第 5 步：接入模型并完成上板验收

在板级工程中加入分类核心、模型存储文件、UART 和控制模块。
把同一批测试图片从电脑送入 FPGA，记录真实标签、Python 整数预测和 FPGA 预测。
检查复位、连续图片、断帧后的恢复，记录资源、布局布线后的时序以及实测延迟。

**验收：**硬件输出与 Python 整数模型逐张一致；满足时序；留有实际串口验证记录。
全部通过后，本实验才能标记“部署完成”。

## 可提前运行：核心综合

不依赖板卡引脚，可以先查看推理核心的资源占用：

```powershell
New-Item -ItemType Directory -Force experiments\01_digits_linear\build\vivado | Out-Null
Push-Location experiments\01_digits_linear\build\vivado
try {
    & 'F:\Xilinx\Vivado\2023.2\bin\vivado.bat' -mode batch -nojournal -nolog -source ..\..\scripts\synth_core.tcl
    if ($LASTEXITCODE -ne 0) { throw 'Vivado synthesis failed' }
} finally {
    Pop-Location
}
```

其他电脑请替换 Vivado 安装路径。输出在 `build/vivado/`。
这是 out-of-context 核心综合，10 ns 只是探索性的目标时钟周期。
综合估计不能证明布线后达到 100 MHz，也不能证明板上接口正确。

## 下一轮实验

实验 01 真正上板后，再依次尝试：带隐藏层的 MLP → MNIST 小 CNN →
流水线和并行 MAC → 更低位宽量化 → 摄像头 → HLS/自动转换工具 → 其他板卡。
每轮只增加少量新问题，并保留旧实验作为可比较的基线。
