# GitHub 留档与恢复

## 提交内容

提交说明文档、实验源码、XDC、Tcl/Python 脚本、仿真、教程、`baseline/` 模型快照和
`reports/` 实测记录。原始结果保留每张图的分数，便于复核 433/450 的准确率。

`.gitignore` 排除了 `.venv/`、`build/`、`board/vendor/`、Vivado 临时文件与生成的 `.bit`。
不要使用 `git add -f` 强行加入这些目录；源码归档无需上传安装包、视频和厂商整套资料。
本仓库另存了模型快照，因此恢复历史模型不依赖本机 `build/`。

## 首次提交和上传

本仓库已完成首次提交并上传至 [GitHub](https://github.com/ZhuJian-fdu/fpga_ai_deployment)，分支为 `main`。
以下保留首次创建其他仓库时的操作参考；本仓库后续更新请使用下一节，不要重复添加 `origin`。
命令在仓库根目录手动执行：

```powershell
git status --short
git add --dry-run .
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Archive ACX720-V3 integer digits inference experiment"
```

检查暂存列表中没有 `vendor/`、`.venv/`、`build/` 后再提交。
如 Git 要求身份，设置自己希望随提交公开的姓名与邮箱（可以使用 GitHub 提供的 noreply 邮箱）。
无需将登录令牌写入仓库文件或远程 URL。

在自己的 GitHub 账号下创建空仓库，不在网页初始化 README 等文件。
将 `YOUR_ACCOUNT` 替换为账号，并按实际仓库名修改 URL：

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/fpga_ai_deployment.git
git push -u origin main
```

如果已经配置过 `origin`，先用 `git remote -v` 检查，不要重复添加或使用强制推送。
许可证尚未选择；需要向他人明确授予复用权限时，再单独决定并添加 LICENSE。

## 已上传仓库的后续更新

每次整理好新代码或实验记录后，检查改动，再提交并推送：

```powershell
git status --short
git diff
git add .
git diff --cached --check
git diff --cached --stat
git commit -m "Describe the changes in this update"
git push
```

如果推送提示远程有新提交，先查看远程变化并合并，不使用强制推送覆盖历史。

## 在新的本地克隆中恢复

以下命令以 Windows PowerShell 为例，在仓库根目录运行；需要 Python 3.11，
仿真需要 Icarus 的 `iverilog` 和 `vvp` 位于 PATH，构建使用本次验证过的 Vivado 2023.2。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r experiments\01_digits_linear\requirements.txt
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\restore_baseline.py
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py classifier
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py protocol
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py ai_uart
.\.venv\Scripts\python.exe experiments\01_digits_linear\scripts\simulate.py ai_reset
```

继续按 [AI 上板教程](../experiments/01_digits_linear/docs/ai_bringup.md) 构建、下载和实测。
教程中的 `F:/GitHubProjects/fpga_ai_deployment`、Vivado 安装路径和 `COM11` 是首次实验的本机示例，
换电脑时必须分别替换为克隆路径、工具安装路径和实际串口号。源码脚本以自身位置定位实验目录。

`reports/` 是 2026-11-24 的历史实测证据，不是新电脑运行的结果。新运行先写到 `build/`；
复测后再有意识地新增或更新归档记录。
构建清单中的 `.bit` 和报告哈希记录当时的文件身份，不承诺不同目录或环境重建会逐字节相同。
Git 可能规范化源码换行；历史源码哈希应按当时的原始字节理解。

## 后续实验

保留 `experiments/01_digits_linear/` 的基线，增加新模型或更换板卡时新建
`experiments/02_name/` 等目录，并更新根目录实验索引。每个实验记录模型来源、
板卡/器件、工具版本、复现命令和真实验收结果。
