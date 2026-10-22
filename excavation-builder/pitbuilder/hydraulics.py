# 【模块中文说明】
# 按施工阶段编译水力设施、外边界及墙体漏水段。
# equivalent_head 是指定总水头的水平等效控制线；drain 为有明确位置的正常排水线。
# 通过实际祖先链控制漏水启停，避免漏水条件扩散到无关施工分支。
# 有限墙阻力只分配墙外侧，内侧取 0；保留土体不会为降水而设成 Dry。
# seepage 接受显式布尔值或 true/false 文字；正向入渗不能代替坑内自然出流。
# 
import copy
import math

# 根据配置、完整施工状态和几何范围返回 {阶段ID: 水力状态}。
# 先验证设施坐标、排水方式和开关，再沿阶段祖先链计算漏水生效区间。
# 每期只保留当前控制方案；控制线被挖到空区、同面冲突或未安装围护就漏水时拒绝生成。
def compile_hydraulics(config,stages,geometry_plan):
    plans={p['id']:copy.deepcopy(p) for p in config['hydraulic_plans']};out={}
    for plan in plans.values():
        flag=plan.get('seepage',False)
        # 不能直接使用 bool(字符串)：Python 会把非空的 false 也视为 True。
        # 只接受明确的 true/false 文字，其他填法交由后续类型检查拒绝。
        if isinstance(flag,str) and flag.strip().lower() in ['true','false']:flag=flag.strip().lower()=='true'
        if not isinstance(flag,bool):raise ValueError('seepage 只能填写布尔值 true/false')
        plan['seepage']=flag
        pts=plan.get('points')
        if not pts or len(pts)<2 or any(len(p)!=2 for p in pts):raise ValueError('必须明确排水位置坐标')
        if plan['mode'] not in ['equivalent_head','drain']:raise ValueError('不支持的排水方式，不能以入渗替代坑内出水')
        if not isinstance(plan.get('head'),(float,int)) or not math.isfinite(plan['head']):raise ValueError('目标总水头无效')
        for x,y in pts:
            if not geometry_plan['left']<=x<=geometry_plan['right']:raise ValueError('坑内排水设施超出围护范围')
            if not geometry_plan['bounds'][1]<=y<=geometry_plan['bounds'][3]:raise ValueError('排水设施超出模型高度')
        if plan['mode']=='drain' and any(plan['head']<p[1]-1e-7 for p in pts):raise ValueError('正常排水线不能施加低于排水线的水头以产生吸力')
        if plan['mode']=='equivalent_head' and max(p[1] for p in pts)-min(p[1] for p in pts)>1e-7:raise ValueError('等效控制线必须水平')
    order={s['id']:i for i,s in enumerate(stages)}
    # 为每期保存整条真实前序祖先链。
    # first 和 last 必须处于同一路径，生效阶段取该路径中间部分，避免按行号把无关分支也判为漏水。
    ancestors={}
    for s in stages:
        ancestors[s['id']]=set(ancestors.get(s['previous_id'],set()))|{s['id']}
    for leak in config['leaks']:
        if leak['first'] not in ancestors[leak['last']]:raise ValueError('漏水起止阶段必须位于同一前后继路径')
    for stage in stages:
        if stage.get('calculation_type')=='Safety':
            if any(leak['first']==stage['id'] for leak in config['leaks']):raise ValueError('安全分析阶段不能作为漏水条件改变的起始阶段')
            out[stage['id']]=copy.deepcopy(out[stage['previous_id']])
            continue
        plan=copy.deepcopy(plans.get(stage['hydraulic_plan_id']))
        if plan and max(p[1] for p in plan['points'])>stage['excavation_y']+1e-7:raise ValueError('控制线已处于开挖空区，请替换水力方案')
        if plan and plan.get('seepage') and stage['operation']!='initial' and stage['excavation_y'] in geometry_plan['excavation_cuts'] and all(abs(p[1]-stage['excavation_y'])<=1e-7 for p in plan['points']):raise ValueError('同一暴露面不能同时指定控制水头和Seepage')
        leaks=[]
        for leak in config['leaks']:
            if leak['first'] in ancestors[stage['id']] and stage['id'] in ancestors[leak['last']]:
                if not stage['walls_active']:raise ValueError('墙尚未安装，不能启用墙体漏水')
                leaks.append(dict(leak,outside_resistance_days=leak['resistance_days'] if leak['mode']=='resistance' else 0,inside_resistance_days=0))
        out[stage['id']]={'boundary':plan,'leaks':leaks,'dry_active_soils':False,
                          'flow_boundaries':config['project']['flow_boundaries'],
                          'initial_water':config['project']['initial_water']}
    return out
