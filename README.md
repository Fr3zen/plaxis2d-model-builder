# PLAXIS 2D 快速建模工具

从 Excel 钻孔和施工参数生成可检查的地层剖面、基坑施工阶段及 PLAXIS 2D 原生模型。

版本：0.1.0-beta.1。MIT 许可证。当前为本地发布候选版本，未上传远程仓库。

## 包含哪些工具

| 入口 | 用途 |
| --- | --- |
| `excavation-builder/检查与预览.cmd` | 校验基坑 Excel，生成逐阶段图像和 HTML 预览 |
| `excavation-builder/基坑自动建模.cmd` | 校验后在新工程中创建地层、结构、水条件和施工阶段，保存并回读 |
| `excel-import/导入Excel钻孔.cmd` | 仅从钻孔 Excel 导入 PLAXIS 原生钻孔和地层 |
| `generate_strata.py` | 根据 JSON 离线生成分层几何与剖面预览 |

支持统一层序钻孔插值、零厚度层/尖灭、按相邻土层切分墙体界面、支撑预应力和四种施工计算类型。默认不划网格、不执行计算。示例均为软件验证用合成参数，不是工程设计值。

## 开始使用

1. 完整解压，保留三个模块的相对目录。
2. 按 [安装与运行](docs/INSTALL.md) 配置离线 Python、PLAXIS 和匹配的 PLAXIS Python。
3. 复制 `excavation-builder/基坑建模模板.xlsx`，填入自己的输入。
4. 先运行检查与预览，确认后再生成新工程。启动原生建模前关闭已有 PLAXIS Input。

```powershell
python -m pip install -r requirements.txt
python excavation-builder/builder.py --excel excavation-builder/基坑建模模板.xlsx --output output/demo.p2dx --validate-only
```

上面仅作离线检查，不需要 PLAXIS 许可。生成原生工程需要单独安装且获授权的 PLAXIS、匹配 SDK 与所用功能的许可。

## 文档

- [输入与建模规则](docs/INPUTS.md)
- [水条件、降水与 Dry](docs/HYDRAULICS.md)
- [验证范围和限制](docs/VALIDATION.md)
- [开发与贡献](CONTRIBUTING.md)
- [第三方依赖与分发边界](THIRD_PARTY_NOTICES.md)
- [发布前清单](docs/RELEASING.md)

本项目独立开发，与 Bentley / Seequent 无隶属或官方背书关系。MIT 仅覆盖本项目可授权的代码、文档和合成示例，不授予 PLAXIS、SDK、第三方本构或第三方工程数据的使用权。
