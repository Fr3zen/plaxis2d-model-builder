# 【模块中文说明】
# 基坑工具与 PLAXIS SDK 之间的独立进程入口。
# 读取父进程生成的 payload，把命令行 mesh-check 标志传给原生适配器。
# 成功写 native_result.json；异常写 failure.txt，并以退出码 1 通知父进程。
# 命令行参数解析位于主入口保护中；导入模块本身不会自动建立模型。
# 
import argparse
import json
from pathlib import Path
import traceback
from pitbuilder.plaxis_adapter import build_project

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--plaxis',type=Path,required=True)
    ap.add_argument('--mesh-check',action='store_true');ns=ap.parse_args()
    try:
        p=json.loads(ns.payload.read_text(encoding='utf-8'))
        p['mesh_check']=ns.mesh_check
        if ns.output.exists() or Path(str(ns.output)+'dat').exists():raise ValueError('目标工程已存在')
        result=build_project(p['config'],ns.output,ns.plaxis,ns.payload.parent,payload=p)
        (ns.payload.parent/'native_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        (ns.payload.parent/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        traceback.print_exc();raise SystemExit(1)
