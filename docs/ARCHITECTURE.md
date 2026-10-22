# 代码结构

`generate_strata.py` 负责钻孔插值和离线分层几何。`excel-import/excel_to_plaxis.py` 负责 XLSX 基础读取和钻孔原生导入；`plaxis_worker.py` 在软件 Python 中运行。

`excavation-builder/builder.py` 是基坑入口：读表、校验、编译阶段、生成预览，再按需调用独立 `worker.py`。`pitbuilder/legacy.py` 按相对位置复用前两个模块，因此不能只复制 excavation-builder 一个目录。

| 模块 | 职责 |
| --- | --- |
| workbook / workbook_headers | 表格解析与中英文表头 |
| schema / materials | 输入与材料合同校验 |
| stages / phase_settings | 施工继承、历时与计算类型 |
| geometry / interfaces / region_math | 分区、分层界面与区域归属 |
| hydraulics | 每期局部水力条件与漏水启停 |
| preview | 输入条件预览，不生成计算云图 |
| plaxis_adapter | 官方脚本接口建模及阶段赋值 |
| verify | 属性比较、保存与重开核查 |

`tools/run_checks.py` 执行离线检查；`tools/package_release.py` 按白名单打包公开文件。Excel 模板作者脚本位于 authoring 和 excel-import/build_template.mjs，仅在已获得相应作者工具的环境再生成模板。公开 XLSX 已生成，终端使用者不需要 Node 作者工具。
