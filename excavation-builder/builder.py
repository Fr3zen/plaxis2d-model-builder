# 【模块中文说明】
# 基坑自动建模的用户入口。
# 先离线读取 Excel/JSON，编译阶段、几何及水力计划，生成逐阶段输入预览与来源哈希。
# 只有未选 --validate-only 时才调用独立 worker；工作进程使用匹配的 PLAXIS Python。
# 状态 input_validated 只代表输入通过检查，model_saved_verified 才代表软件写入和保存重开回读通过。
# 本入口默认不划分网格、不计算；报告目录已存在也拒绝重用，保证失败诊断能够保留。
# 
"""Excel-to-PLAXIS input builder. Defaults to no meshing and no calculation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from pitbuilder.verify import check_output

ROOT=Path(__file__).resolve().parent
PLAXIS=Path(r'E:\plaxis2024 2d\Plaxis2DXInput.exe')
PLX_PY=Path(r'C:\ProgramData\Seequent\PLAXIS Python Distribution V2\python\python.exe')

# 纯离线准备阶段：检查输出冲突，读取并验证配置，编译完整阶段、几何和水力计划。
# 写 payload.json、输入预览和 report.json，返回诊断路径及 input_validated 状态。
# 不启动 PLAXIS；此时还没有证明原生模型可以写入。
def prepare(excel,output):
    from pitbuilder.workbook import read_workbook
    from pitbuilder.stages import compile_stages
    from pitbuilder.geometry import plan_geometry
    from pitbuilder.hydraulics import compile_hydraulics
    from pitbuilder.preview import write_preview
    report_dir=check_output(output)
    if Path(excel).suffix.lower()=='.json':
        from pitbuilder.schema import validate_config
        c=validate_config(json.loads(Path(excel).read_text(encoding='utf-8')),Path(excel).parent)
    else:c=read_workbook(excel)
    stages=compile_stages(c);geo=plan_geometry(c,stages);hyd=compile_hydraulics(c,stages,geo)
    # payload 是外层几何环境与软件工作进程之间的合同。
    # 只包含可序列化配置和编译状态，Shapely 对象不直接跨进程传递。
    payload={'config':c,'stages':stages,'geometry':geo,'hydraulics':hyd}
    report_dir.mkdir(parents=True)
    (report_dir/'payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    preview=write_preview(c,geo,stages,hyd,report_dir)
    result={'status':'input_validated','excel':str(Path(excel).resolve()),'source_sha256':hashlib.sha256(Path(excel).read_bytes()).hexdigest(),
            'project':str(Path(output).resolve()),'report_dir':str(report_dir),'preview':preview,
            'calculation_requested':False,'mesh_requested':False}
    (report_dir/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

# 解析命令行/文件选择结果并组织用户入口流程。
# 先离线验证，再按选项调用匹配 Python 的软件工作进程；取消选择正常返回，异常返回非零状态。
# 最终成功状态必须来自工作进程结果，不能仅凭命令发出就报告模型已生成。
def main(argv=None):
    parser=argparse.ArgumentParser(description='Excel 基坑自动建模；默认只建模，不计算。')
    inputs=parser.add_mutually_exclusive_group();inputs.add_argument('--excel',type=Path);inputs.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--validate-only',action='store_true');parser.add_argument('--mesh-check',action='store_true')
    parser.add_argument('--plaxis',type=Path,default=PLAXIS);parser.add_argument('--plaxis-python',type=Path,default=PLX_PY)
    args=parser.parse_args(argv);args.excel=args.excel or args.config;gui=args.excel is None;window=None
    try:
        if gui:
            import tkinter as tk
            from tkinter import filedialog,messagebox
            window=tk.Tk();window.withdraw()
            chosen=filedialog.askopenfilename(title='选择基坑建模 Excel',initialdir=ROOT,filetypes=[('Excel','*.xlsx')])
            if not chosen:return 0
            args.excel=Path(chosen)
            if args.output is None:
                selected=filedialog.asksaveasfilename(title='选择新的模型保存位置（检查模式仅生成旁边的预览目录）',initialdir=ROOT/'output',defaultextension='.p2dx',filetypes=[('PLAXIS','*.p2dx')])
                if not selected:return 0
                args.output=Path(selected)
        if args.output is None:raise ValueError('命令行需指定 --output 新工程路径')
        result=prepare(args.excel,args.output)
        if gui:
            import os
            os.startfile(result['preview']['html'])
        if not args.validate_only:
            if gui and not messagebox.askyesno('生成模型','分期预览已打开。确认条件后，是否现在生成新模型？\n不会运行计算。'):return 0
            cmd=[str(args.plaxis_python),'-u',str(ROOT/'worker.py'),'--payload',str(Path(result['report_dir'])/'payload.json'),
                 '--output',str(args.output.resolve()),'--plaxis',str(args.plaxis)]
            if args.mesh_check:cmd.append('--mesh-check')
            # 独立进程隔离 Python/SDK 版本；返回码非零则诊断目录保留，不能把离线预览状态当作建模成功。
            proc=subprocess.run(cmd)
            if proc.returncode:raise RuntimeError('模型未完成；诊断目录：'+result['report_dir'])
            result.update(json.loads((Path(result['report_dir'])/'native_result.json').read_text(encoding='utf-8')))
        (Path(result['report_dir'])/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if gui:messagebox.showinfo('完成','状态：'+result['status']+'\n记录：'+result['report_dir'])
        return 0
    except Exception as error:
        print('建模失败：'+str(error),file=sys.stderr,flush=True)
        if gui:
            from tkinter import messagebox
            messagebox.showerror('建模失败',str(error))
        return 1
    finally:
        if window is not None:window.destroy()

if __name__=='__main__':raise SystemExit(main())
