# 【模块中文说明】
# 集中校验几何、材料、阶段和水条件之间的引用关系。
# 输入 raw 是 Excel/JSON 得到的字典；base_dir 用于解析相对 DLL 路径。
# 先深复制，避免排序及路径规范化改变调用者的原对象；通过后返回可交给各编译器的配置。
# 当前合同为双侧竖直围护、明确地层材料映射、不重叠的局部水分区；不默补未知工程参数。
# 
import copy
import math
from pathlib import Path
from .legacy import build_model
from .materials import material_requests

# 递归检查字典和列表中的浮点值，遇 NaN/无穷值报告所在输入路径，防止非法值进入几何与软件参数。
def finite(value,path):
    if isinstance(value,float) and not math.isfinite(value):raise ValueError(path+' 含无效数值')
    if isinstance(value,dict):
        for k,v in value.items():finite(v,path+'.'+k)
    if isinstance(value,list):
        for v in value:finite(v,path)

# 校验一张编号表中的 ID 均为非空字符串且不重复，返回编号集合，供后续跨表引用检查。
def unique(rows,label):
    ids=[v['id'] for v in rows]
    if any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids))!=len(ids):raise ValueError(label+' ID重复或为空')
    return set(ids)

# 统一输入合同入口：深复制配置后验证范围、地层、材料、结构、阶段和水位分区。
# base_dir 只用于解析相对 DLL 路径；编号引用不自动补齐，初始阶段 INITIAL 为保留名称。
# 返回规范化后的配置；物理设施与阶段组合的更细水力限制由 compile_hydraulics 继续检查。
def validate_config(raw,base_dir):
    c=copy.deepcopy(raw);finite(c,'输入')
    if c.get('schema_version')!=1:raise ValueError('不支持的配置版本')
    required=['project','geology','layer_materials','materials','walls','structures','stages','hydraulic_plans','leaks','water_regions']
    if any(k not in c for k in required):raise ValueError('缺少必要输入表')
    build_model(c['geology'])
    # 范围顺序统一为 xmin、ymin、xmax、ymax；坐标是绝对标高，不能把层厚当作 y。
    # 首末孔必须覆盖左右模型边界，避免在没有来源说明时自行向剖面外延伸地层。
    p=c['project'];xmin,ymin,xmax,ymax=p['bounds']
    if not xmin<xmax or not ymin<ymax or 'start_y' not in p:raise ValueError('工程范围/施工起始标高无效')
    holes=c['geology']['boreholes']
    if min(h['x'] for h in holes)!=xmin or max(h['x'] for h in holes)!=xmax:raise ValueError('首末钻孔必须覆盖左右模型边界')
    if min(h['bottoms'][-1] for h in holes)<ymin or max(h['ground'] for h in holes)>ymax:raise ValueError('地层超出模型范围')
    ids=unique(c['materials'],'材料')
    for m in c['materials']:
        if m.get('dll_path'):m['dll_path']=str((Path(base_dir)/m['dll_path']).resolve())
    material_requests(c)
    # 材料编号的存在性和材料类别分别检查：存在的 soil 材料也不能直接赋给墙板。
    # 每一逻辑层都必须有明确赋材映射，零厚度层也不从这张映射中删掉。
    kinds={m['id']:m['kind'] for m in c['materials']}
    if set(c['layer_materials'])!=set(l['id'] for l in c['geology']['layers']):raise ValueError('地层材料映射不完整')
    if any(v not in ids for v in c['layer_materials'].values()):raise ValueError('地层引用未知材料')
    if any(kinds[v]!='soil' for v in c['layer_materials'].values()):raise ValueError('地层必须引用土体材料')
    if len(c['walls'])!=2:raise ValueError('第一版要求两侧竖直围护')
    wallids=unique(c['walls'],'围护');c['walls'].sort(key=lambda w:w['x'])
    if not xmin<c['walls'][0]['x']<c['walls'][1]['x']<xmax:raise ValueError('墙位置必须在模型内且左右分开')
    for w in c['walls']:
        if not ymin<=w['bottom']<w['top']<=ymax:raise ValueError('墙顶/底无效')
        choice=w.get('interface_material','AUTO')
        w['interface_material']='AUTO' if choice in [None,'','AUTO','自动','按相邻土层'] else choice
        if w['material'] not in ids or kinds[w['material']]!='plate':raise ValueError('围护必须引用板材料')
        if w['interface_material']!='AUTO' and (w['interface_material'] not in ids or kinds[w['interface_material']]!='soil'):raise ValueError('界面自定义覆盖必须引用土体材料；分层自动模式填AUTO')
        from .interfaces import wall_segments
        wall_segments(c,w)
    structures=unique(c['structures'],'结构')
    for st in c['structures']:
        if st['material'] not in ids or st['kind'] not in ['anchor','slab','beam']:raise ValueError('结构类型或材料无效')
        if kinds[st['material']]!=('anchor' if st['kind']=='anchor' else 'plate'):raise ValueError('结构材料类型不匹配')
    # 按表中顺序建立已知前序集合，拒绝向后引用和环；真正的分支继承在阶段编译器中处理。
    # INITIAL 只由工具创建，用户阶段不允许同名，以免覆盖初始状态。
    stageids=unique(c['stages'],'阶段');seen={'INITIAL'}
    if 'INITIAL' in stageids:raise ValueError('INITIAL 是初始阶段保留ID')
    for st in c['stages']:
        if st['previous'] not in seen:raise ValueError('阶段前序无效/有环，需按前后顺序排列')
        seen.add(st['id'])
        if any(k not in structures for k in st.get('structure_ids',[])):raise ValueError('阶段引用未知结构')
    plans=unique(c['hydraulic_plans'],'水力方案')
    for st in c['stages']:
        if st.get('hydraulic_plan') and st['hydraulic_plan'] not in plans:raise ValueError('未知水力方案')
    unique(c['leaks'],'漏水段')
    order={s['id']:i for i,s in enumerate(c['stages'])};walls={w['id']:w for w in c['walls']}
    for leak in c['leaks']:
        if leak['wall'] not in wallids:raise ValueError('未知漏水墙')
        w=walls[leak['wall']]
        if not w['bottom']<=leak['bottom']<leak['top']<=w['top']:raise ValueError('漏水范围超出墙体')
        if leak['first'] not in stageids or leak['last'] not in stageids or order[leak['first']]>order[leak['last']]:raise ValueError('漏水阶段范围无效')
        if leak['mode'] not in ['resistance','permeable']:raise ValueError('未知漏水类型')
        if leak['mode']=='resistance' and leak.get('resistance_days',0)<=0:raise ValueError('水力阻力需为正，单位day')
    # 相邻漏水段允许共用一个端点；只有竖向范围和阶段区间都实质交叠才拒绝。
    # 这里先做顺序区间检查，水力编译器还会检查 first/last 是否位于同一祖先链。
    for i,a in enumerate(c['leaks']):
        for b in c['leaks'][i+1:]:
            if a['wall']==b['wall'] and min(a['top'],b['top'])>max(a['bottom'],b['bottom'])+1e-7 and min(order[a['last']],order[b['last']])>=max(order[a['first']],order[b['first']]):raise ValueError('漏水段时空范围重叠')
    # 初始水位线按 x 严格递增，并覆盖整个模型；水头值并非土层层底标高。
    points=p['initial_water']
    if len(points)<2 or any(points[i][0]>=points[i+1][0] for i in range(len(points)-1)):raise ValueError('初始水位控制点按x严格递增')
    if points[0][0]>xmin or points[-1][0]<xmax:raise ValueError('初始水位未覆盖边界')
    from shapely.geometry import Polygon,box
    # 局部水位需要明确的空间分区，分区必须有效、在域内且互不重叠。
    # 通过此输入检查不代表每个原生切分土簇都可无歧义归类，写入阶段还会做包围盒完整包含检查。
    polygons=[];unique(c['water_regions'],'局部水条件')
    for region in c['water_regions']:
        poly=Polygon(region['polygon'])
        if not poly.is_valid or poly.area<=0 or poly.difference(box(xmin,ymin,xmax,ymax)).area>1e-7:raise ValueError('局部水分区几何无效或超出范围')
        if any(poly.intersection(other).area>1e-7 for other in polygons):raise ValueError('局部水条件区域重叠')
        polygons.append(poly)
        wp=region['points']
        if len(wp)<2 or any(wp[i][0]>=wp[i+1][0] for i in range(len(wp)-1)) or wp[0][0]>poly.bounds[0] or wp[-1][0]<poly.bounds[2]:raise ValueError('局部水位控制点未按x递增覆盖分区')
    if set(p['flow_boundaries'])!={'BoundaryXMin','BoundaryXMax','BoundaryYMin','BoundaryYMax'} or any(v not in ['Open','Closed'] for v in p['flow_boundaries'].values()):raise ValueError('需明确四个外边界Open/Closed')
    from .stages import compile_stages
    compile_stages(c)
    return c
