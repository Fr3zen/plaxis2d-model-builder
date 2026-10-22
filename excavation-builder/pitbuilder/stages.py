# 【模块中文说明】
# 把增量施工记录编译为每个阶段的完整状态。
# 每行 previous 指向真实前序，支持分支；不能简单把表格上一行当成前序。
# 施工阶段仅使用显式阶段历时，单位 day；逐阶段选择计算类型。
# new_structure_ids 与 active_structure_ids 分开保存，防止已经安装的支撑在后续阶段重复张拉。
# 输出仅是阶段输入设置，不表示实际计算时间响应或连续移动的开挖面。
# 
import copy
import math
from .phase_settings import calculation_type,pore_pressure_type

# 把每行施工操作应用到其真实 previous 阶段的深拷贝，返回含 INITIAL 的完整阶段列表。
# 没有墙/结构/水方案变化的字段从前序继承，新安装结构列表每期重新置空。
# 固结/完全耦合历时为正；塑性/安全允许零历时，开挖面只能下降。
def compile_stages(config):
    if 'start_y' not in config['project']:raise ValueError('必须明确施工起始标高')
    initial={'id':'INITIAL','previous_id':None,'operation':'initial','duration_days':0,
             'excavation_y':config['project']['start_y'],'active_structure_ids':[],'new_structure_ids':[],
             'walls_active':False,'hydraulic_plan_id':None,'calculation_type':'K0 procedure','pore_pressure_type':'Phreatic'}
    states=[initial];byid={'INITIAL':initial};structures={s['id']:s for s in config['structures']}
    for row in config['stages']:
        if row['previous'] not in byid:raise ValueError('无效前序阶段')
        # 按真实前序深复制完整状态，分支之间互不污染。
        # 每期清空新安装标记，但保留已激活结构，这两个列表承担不同的预应力含义。
        st=copy.deepcopy(byid[row['previous']]);st.update(id=row['id'],previous_id=row['previous'],operation=row['operation'],new_structure_ids=[])
        op=row['operation']
        if op not in ['walls','dewater','excavate','support','wait','slab']:raise ValueError('未知施工操作')
        if row.get('speed_m_day') not in [None,''] or row.get('等效开挖速度（m/天）') not in [None,'']:
            raise ValueError('等效开挖速度已取消，请删除速度输入并填写阶段历时（天）')
        kind=calculation_type(row.get('calculation_type','Consolidation'))
        if kind=='Safety' and (op!='wait' or row.get('hydraulic_plan') or row.get('structure_ids') or row.get('excavation_y') is not None):
            raise ValueError('安全分析阶段仅允许 wait，继承前序工况，不得改变开挖、结构或水力方案')
        dt=row.get('duration_days')
        if op=='excavate':
            new=row['excavation_y'];thickness=st['excavation_y']-new
            if thickness<=0:raise ValueError('开挖面必须下降，不支持回填')
            st['excavation_y']=new
        if dt is None or not isinstance(dt,(float,int)) or isinstance(dt,bool) or not math.isfinite(dt) or dt<0:raise ValueError('阶段历时必须填写有限非负数，单位天')
        if kind in ['Consolidation','Fully coupled flow-deformation'] and dt==0:raise ValueError('固结和完全耦合阶段历时必须大于0天')
        st['duration_days']=dt;st['calculation_type']=kind
        if op=='walls':st['walls_active']=True
        # 安装结构必须已经暴露，即安装标高不低于当前开挖面；这只校验标高条件。
        # 同一条前序链中重复列出已激活结构不会再次加入 new_structure_ids。
        if op in ['support','slab']:
            if not row.get('structure_ids'):raise ValueError('需明确安装结构')
            for sid in row['structure_ids']:
                obj=structures[sid]
                if obj['y']<st['excavation_y']-1e-7:raise ValueError('安装位置尚未开挖暴露')
                if sid not in st['active_structure_ids']:
                    st['active_structure_ids'].append(sid);st['new_structure_ids'].append(sid)
        if row.get('hydraulic_plan'):st['hydraulic_plan_id']=row['hydraulic_plan']
        st['pore_pressure_type']=pore_pressure_type(kind,row.get('pore_pressure_type'))
        states.append(st);byid[st['id']]=st
    return states
