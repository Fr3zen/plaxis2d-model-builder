# 【模块中文说明】
# 输出保护与嵌套状态差异比较。
# 新工程必须同时避开已有 p2dx、p2dxdat 和 _builder 目录，防止覆盖原工程或诊断记录。
# 比较器返回差异列表：空列表为一致，非空列表保留具体属性路径和期望/实际值。
# 浮点数按绝对和相对容差比较，布尔值则严格比较类型，避免 True 被当作数值 1。
# 
import math
from pathlib import Path

# 检查扩展名为 p2dx，并确保工程、配套 dat 目录和诊断目录都不存在。
# 返回将使用的 _builder 目录路径，本函数只检查，不创建文件夹。
def check_output(output):
    p=Path(output).resolve()
    if p.suffix.lower()!='.p2dx':raise ValueError('输出必须为 .p2dx')
    paths=[p,Path(str(p)+'dat'),p.parent/(p.stem+'_builder')]
    if any(x.exists() for x in paths):raise ValueError('工程或记录目录已存在，拒绝覆盖')
    return paths[2]

# 递归比较字典、列表和标量，返回精确到阶段/对象/属性的差异列表。
# 数值允许微小绝对/相对误差，bool 先于数值分支比较，列表长度或缺键也会报告。
def compare_state(expected,actual,path=''):
    result=[]
    if isinstance(expected,dict) and isinstance(actual,dict):
        for k in sorted(set(expected)|set(actual)):
            key=path+'.'+k if path else k
            if k not in expected or k not in actual:result.append({'path':key,'expected':expected.get(k),'actual':actual.get(k)})
            else:result.extend(compare_state(expected[k],actual[k],key))
        return result
    if isinstance(expected,list) and isinstance(actual,list):
        if len(expected)!=len(actual):return [{'path':path,'expected':expected,'actual':actual}]
        for i,(a,b) in enumerate(zip(expected,actual)):result.extend(compare_state(a,b,path+'['+str(i)+']'))
        return result
    if isinstance(expected,bool) or isinstance(actual,bool):same=type(expected)==type(actual) and expected==actual
    elif isinstance(expected,(int,float)) and isinstance(actual,(int,float)):
        same=math.isfinite(actual) and math.isclose(expected,actual,abs_tol=1e-7,rel_tol=1e-8)
    else:same=expected==actual
    return [] if same else [{'path':path,'expected':expected,'actual':actual}]
