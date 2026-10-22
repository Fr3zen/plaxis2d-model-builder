# 安装与运行

## 两套 Python

离线环境运行 Excel 解析、Shapely 几何处理和 Matplotlib 预览。建议使用 Windows x64、Python 3.8 或更新版本；版本实际兼容性以测试记录为准。安装 `requirements.txt`，并确保 tkinter 可用（文件选择窗口需要）。

PLAXIS 环境运行 `worker.py` 和官方 `plxscripting`。使用与安装版本匹配的官方 Python/SDK。不要把任意 pip 版本的 SDK 当成跨版本兼容保证，也不要把离线环境直接替换为软件工作进程环境。

## 配置 CMD

`excavation-builder/run_builder.cmd` 中的 `PIT_PYTHON` 目前保留原机默认 `E:\pyt\python.exe`。其他机器必须改为自己的离线 Python 绝对路径。

PLAXIS 程序默认路径为 `E:\plaxis2024 2d\Plaxis2DXInput.exe`，官方 Python 默认路径为 `C:\ProgramData\Seequent\PLAXIS Python Distribution V2\python\python.exe`。这两个路径是安装示例，不是打包的运行时。

可以不改 Python 源码，显式传参：

```powershell
python excavation-builder/builder.py --excel excavation-builder/基坑建模模板.xlsx --output output/my_pit.p2dx --plaxis "D:\Apps\PLAXIS\Plaxis2DXInput.exe" --plaxis-python "D:\Apps\PLAXISPython\python.exe"
```

双击入口同样可在调用后附加 `--plaxis`、`--plaxis-python`；也可在 CMD 的 `call` 行中写入本机路径。`excel-import/导入Excel钻孔.cmd` 使用 `PLUGIN_PYTHON`，需分别配置。所有 CMD 均应从完整解压目录运行。

## 操作顺序

保存输入表 → 检查与预览 → 核对各阶段 → 关闭已打开的 Input → 选择新的模型路径 → 建模保存 → 检查回读报告 → 自行划网格和计算。

不要覆盖已有工程。失败时保留旁边的 `_builder` 诊断目录。`.p2dx` 和对应 `.p2dxdat` 是一套工程文件，转移时需一起保留。

本包不附带 Python、PLAXIS、官方 SDK、本构 DLL 或安装器。没有 PLAXIS 时仍可执行离线检查与单元测试。
