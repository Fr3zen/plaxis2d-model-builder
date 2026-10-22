# 【模块中文说明】
# 在不复制旧实现的前提下复用钻孔读表与地层生成能力。
# 通过文件位置加载旧导入器，再恢复 sys.path，避免同名 build_distribution 等模块发生误导入。
# 调用旧解析器和几何生成器时也临时恢复搜索路径；这里不启动 PLAXIS。
# 
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pitbuilder_borehole_import', ROOT/'excel-import'/'excel_to_plaxis.py')
importer = importlib.util.module_from_spec(spec)
saved_path=list(sys.path)
try:spec.loader.exec_module(importer)
finally:sys.path[:]=saved_path

# 临时把旧几何生成器目录加入模块搜索路径并调用原实现；无论成功或异常都恢复 sys.path，返回原四元组。
def build_model(data):
    saved=list(sys.path);sys.path.insert(0,str(ROOT))
    try:
        from generate_strata import build_model as build
        return build(data)
    finally:sys.path[:]=saved
read_xlsx = importer.read_xlsx
# 临时补全旧解析器需要的导入路径，返回其原始解析结果；finally 恢复路径，避免同名模块污染。
def parse_cells(*args,**kwargs):
    saved=list(sys.path);sys.path.insert(0,str(ROOT))
    try:return importer.parse_cells(*args,**kwargs)
    finally:sys.path[:]=saved
launch_plaxis = importer.launch_plaxis
