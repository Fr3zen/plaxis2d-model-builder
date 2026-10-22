# 【模块中文说明】
# PLAXIS 2024 本机接口适配层，负责所有原生模型写入和回读。
# 数据流程：材料 → 原生钻孔 → 墙与界面 → 全部切线/水设施 → 水位 → 施工阶段 → 回读 → 保存重开。
# 逻辑编号映射到软件返回的真实对象根名，切分后按根名重新寻找子对象，不写死 Soil_1 等编号。
# 数值单位按 m、kN、day；枚举回读需转换到与请求可比较的形式。
# 默认无网格、无计算；显式 mesh_check 只作网格检查，之后还需保存重开并再次回读。
# 
"""Version-specific PLAXIS writer. No calculation is called by this module."""
import copy
import json
import re
from pathlib import Path
import secrets
import socket
import subprocess
import time
from .verify import compare_state
from .phase_settings import CALCULATION_TYPES,PORE_TYPES,phase_properties
from .interfaces import wall_segments,segment_layer,wall_material_key,horizontal_adjacent_layer

EPS=1e-7

# 用土簇完整包围盒判断该期是否保留：坑外保持激活，坑内开挖面以上停用。
# 坑内外或开挖面被同一土簇跨越时抛错，说明几何尚未正确切开；True 表示激活。
def soil_state(bb,left,right,excavation_y):
    xmin,ymin,xmax,ymax=bb
    if xmax<=left+EPS or xmin>=right-EPS:return True
    if xmin<left-EPS or xmax>right+EPS:raise ValueError('土体跨越坑内外边界，未完成切分')
    if ymin>=excavation_y-EPS:return False
    if ymax<=excavation_y+EPS:return True
    raise ValueError('土体跨越开挖面，未完成切分')

# 明确有限墙阻力的分配约定：外侧承担给定总阻力，内侧为 0。
# 避免把同一个有限阻力同时施加两侧而产生双倍阻水。
def interface_resistances(total):
    return {'outside':total,'inside':0}

# 根据实际几何线首末端 y 和左右墙位置判断墙外侧是否为正界面。
# 不能只按创建时的点顺序猜测；软件可能重新调整线方向，水平线不适用此判断。
def outside_positive(wall_side,first_y,second_y):
    if abs(first_y-second_y)<EPS:raise ValueError('围护方向不能水平')
    return (wall_side=='right')==(second_y<first_y)

# 从材料 echo 文本按属性名抽取一个回读值，并依据请求值类型转成 bool/float/文本。
# 属性名比较忽略大小写；去掉枚举后的数字后缀及数值单位，不用格式差异制造误报。
def material_value(echo,key,expected):
    for line in echo.splitlines():
        if re.match(r'^'+re.escape(key)+r'(?:\s*\([^:]*\))?:',line.strip(),re.IGNORECASE):
            text=line.split(':',1)[1].strip()
            if isinstance(expected,bool):return {'True':True,'False':False}.get(text,text)
            if isinstance(expected,(float,int)):return float(text.split()[0])
            return re.sub(r'\s+\(\d+\)$','',text).strip('"')
    raise RuntimeError('材料回读缺失属性 '+key)

# 取 PLAXIS 标量代理的实际 .value，几何坐标等后续再显式转为 float。
def value(obj):return obj.value
# 读取阶段对象父几何的 BoundingBox，按 xmin、ymin、xmax、ymax 输出浮点列表。
def bbox(obj):
    b=obj.Parent.BoundingBox
    return [float(value(getattr(b,k))) for k in ['xMin','yMin','xMax','yMax']]
# 把属性字典展平成 PLAXIS 接口要求的键、值交替参数序列，保留原字典插入顺序。
def args(props):
    out=[]
    for k,v in props.items():out.extend([k,v])
    return out
# 兼容原生命令返回单对象或对象列表的情况，取列表最后一个特征对象，避免把父几何当作结构特征。
def last(result):return result[-1] if isinstance(result,(list,tuple)) else result
# 按软件返回的根名匹配本体及带下划线后缀的切分子对象；根名应来自当前生成过程而非手写编号。
def children(collection,root):
    return [o for o in collection if str(o.Name)==root or str(o.Name).startswith(root+'_')]

# 创建本工具独占的新 Input 会话，已有 Input 则拒绝启动，避免重置用户工程。
# 只连接刚选出的本地端口，返回 server、g、process；超时不会转而连接其他现有会话。
def launch_owned(executable):
    from .legacy import importer
    if importer.plaxis_running():
        raise ValueError('PLAXIS Input 已运行，请先保存并关闭再生成新模型；不会接管或关闭已有工程。')
    from plxscripting.easy import new_server
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    password=secrets.token_hex(16)
    proc=subprocess.Popen([str(executable),'--AppServerPort='+str(port),'--AppServerPassword='+password],cwd=str(Path(executable).parent))
    until=time.monotonic()+180
    while time.monotonic()<until:
        try:
            s,g=new_server('127.0.0.1',port,password=password,timeout=2,request_timeout=60)
            if s.active:
                if not s.is_2d:raise RuntimeError('不是 PLAXIS 2D 会话')
                return s,g,proc
        except Exception:
            if proc.poll() is not None:raise RuntimeError('PLAXIS 新会话已退出')
            time.sleep(1)
    raise RuntimeError('等待独立 PLAXIS 接口超时；未连接已有工程')

# 有状态原生写入器：缓存逻辑编号与真实对象根名、阶段名、水位名及期望回读值。
# 每次构建使用新的实例；几何生成后才建立土簇缓存，不跨模型复用代理对象。
class NativeBuilder:
    # 保存专用会话、已验证配置及离线 payload，并初始化材料/对象/阶段映射。
    # 左右边界来自两侧围护 x 坐标，所有回读期望值从空集合开始记录。
    def __init__(self,s,g,config,payload,report_dir):
        self.s,self.g,self.c,self.payload,self.report_dir=s,g,config,payload,Path(report_dir)
        self.materials={};self.roots={};self.phase_names={};self.water_names={}
        self.expected={};self.audit=[]
        self.material_expected={};self.wall_positive_outside={}
        self.left,self.right=sorted(w['x'] for w in config['walls'])
        self.interface_segments={w['id']:wall_segments(config,w) for w in config['walls']}

    # 按材料类别选择 soilmat/platemat/anchormat，合并显式覆盖参数并记录回读期望。
    # 先设置本构和排水/结构类型，再设相关刚度参数；UserNuU 等只读相关字段延后判断。
    # 创建 UDSM 后再核对 DLL 实际暴露的用户参数数目，数量不符立即失败。
    def make_material(self,ident,m,extra=None):
        p=copy.deepcopy(m['properties']);p.update(extra or {});p['Identification']=ident;p['Comments']='PITBUILDER:'+ident
        factory={'soil':self.g.soilmat,'plate':self.g.platemat,'anchor':self.g.anchormat}[m['kind']]
        # 先确定材料模式再设置模式相关参数，避免接口在错误材料类型下拒绝 EA/EI 或悄悄保留默认值。
        first=['SoilModel','DrainageType'] if m['kind']=='soil' else ['MaterialType']
        ordered={k:p[k] for k in first if k in p};ordered.update(p)
        # UserNuU is read-only under some UDSM drainage choices; retain and verify
        # the requested value, setting it only when the created dataset differs.
        # 部分排水/UDSM 组合会令 UserNuU 只读。
        # 先创建后读取，只有现值与请求不同时才尝试写入；最终仍由统一材料回读判断是否一致。
        deferred={k:ordered.pop(k) for k in ['UserNuU'] if k in ordered}
        obj=factory(*args(ordered));self.materials[ident]=obj
        for key,wanted in deferred.items():
            current=material_value(self.g.echo(obj),key,wanted)
            if compare_state(wanted,current):self.g.setproperties(obj,key,wanted)
        if m['properties'].get('SoilModel') in ['User-defined',100]:
            count=len(re.findall(r'^\s*User\d+\s*\(',self.g.echo(obj),re.MULTILINE))
            if count!=m['udsm_parameter_count']:raise RuntimeError('DLL实际参数个数与输入声明不一致，拒绝使用默认值补缺')
        self.audit.append({'material':ident,'requested':p,'echo':self.g.echo(obj)})
        self.material_expected[str(obj.Name)]=p
        return obj

    # 按固定依赖顺序建立材料、钻孔、围护、全部切线、水位和施工阶段，再写每期状态。
    # 本函数会对已核对归属的会话执行 new()；普通用户路径必须通过 launch_owned 新建会话。
    # 提前创建未来切线，避免阶段写到一半再改变几何，造成土簇编号和材料映射失效。
    def create(self):
        g=self.g;c=self.c
        self.s.new()
        g.setproperties('Title',c['project']['name'],'UnitLength','m','UnitForce','kN','UnitTime','day','ModelType','Plane strain','ElementType','15-Noded')
        g.SoilContour.initializerectangular(*c['project']['bounds'])
        for m in c['materials']:self.make_material(m['id'],m)
        holes=sorted(c['geology']['boreholes'],key=lambda h:h['x'])
        native=[g.borehole(h['x']) for h in holes]
        # 先创建统一逻辑层序，再按每孔完整层面重设实际标高；临时层厚不用于改变零厚度数据。
        for _ in c['geology']['layers']:g.soillayer(1)
        for src,target in zip(holes,native):
            levels=[src['ground']]+src['bottoms'];settings=[]
            for i,y in enumerate(levels):settings.extend([i,y])
            g.setsoillayerlevel(target,*settings);g.setproperties(target,'Comments',src['id'])
            actual=[float(g.getsoillayerlevel(target,i)) for i in range(len(levels))]
            if compare_state(levels,actual):raise RuntimeError('钻孔标高回读不一致: '+src['id'])
        for i,layer in enumerate(c['geology']['layers']):
            g.setproperties(g.Soillayers[i],'Comments',layer['id'])
            g.setmaterial(g.Soillayers[i].Soil,self.materials[c['layer_materials'][layer['id']]])
            self.roots['layer:'+layer['id']]=str(g.Soillayers[i].Soil.Name)
        g.gotostructures()
        ymin=c['project']['bounds'][1];top=c['project']['start_y']
        # Full-height geometric dividers carry no structure below wall toes.
        for w in c['walls']:
            x=w['x'];g.line((x,ymin),(x,w['top']))
            pl=last(g.plate((x,w['top']),(x,w['bottom'])));g.setmaterial(pl,self.materials[w['material']])
            self.roots['wall:'+w['id']]=str(pl.Name)
            line=pl.Parent
            self.wall_positive_outside[w['id']]=outside_positive('left' if x==self.left else 'right',float(line.First.y.value),float(line.Second.y.value))
            self.roots['pos:'+w['id']]=str(last(g.posinterface(line)).Name)
            self.roots['neg:'+w['id']]=str(last(g.neginterface(line)).Name)
            for segment in self.interface_segments[w['id']]:
                # Force geological contact elevations into the native cut graph.
                # The wall plate stays continuous; interfaces split at crossings.
                g.line((x,segment['top']),(x,segment['bottom']))
                base=next(m for m in c['materials'] if m['id']==segment['material_id'])
                for mode,cross in [('BLOCK','Impermeable'),('OPEN','Fully permeable')]:
                    self.make_material(wall_material_key(mode,w['id'],segment['layer_id']),base,{'CrossPermeability':cross,'DrainageConductivity':0})
        for leak in c['leaks']:
            w=next(w for w in c['walls'] if w['id']==leak['wall']);x=w['x']
            g.point(x,leak['top']);g.point(x,leak['bottom'])
            # Explicit split coordinates are supplied by a collinear line, not standalone points alone.
            # 单独的点不足以保证墙界面按漏水端点切分。
            # 增加同线几何段，让软件生成的界面子段能按完整竖向范围匹配漏水材料。
            g.line((x,leak['top']),(x,leak['bottom']))
            extras={'CrossPermeability':'Fully permeable','DrainageConductivity':0}
            if leak['mode']=='resistance':extras.update(CrossPermeability='Semi-permeable',HydraulicResistance=leak['resistance_days'])
            for segment in self.interface_segments[w['id']]:
                if min(segment['top'],leak['top'])<=max(segment['bottom'],leak['bottom'])+EPS:continue
                base=next(m for m in c['materials'] if m['id']==segment['material_id'])
                self.make_material(wall_material_key('LEAK',w['id'],segment['layer_id'],leak['id']),base,extras)
        if any(st['kind']=='slab' for st in c['structures']):
            for layer_id,material_id in c['layer_materials'].items():
                base=next(m for m in c['materials'] if m['id']==material_id)
                self.make_material('IF-SLAB-'+layer_id,base,{'CrossPermeability':'Impermeable','DrainageConductivity':0})
        for st in c['structures']:
            points=((self.left,st['y']),(self.right,st['y']))
            feature=last(g.n2nanchor(*points) if st['kind']=='anchor' else g.plate(*points))
            g.setmaterial(feature,self.materials[st['material']]);self.roots['structure:'+st['id']]=str(feature.Name)
            if st['kind']=='slab':
                self.roots['slabpos:'+st['id']]=str(last(g.posinterface(feature.Parent)).Name)
                self.roots['slabneg:'+st['id']]=str(last(g.neginterface(feature.Parent)).Name)
        for y in self.payload['geometry']['excavation_cuts']:
            bc=last(g.gwfbc((self.left,y),(self.right,y)))
            self.roots['surface:'+str(y)]=str(bc.Name)
        for hp in c['hydraulic_plans']:
            fn=g.drain if hp['mode']=='drain' else g.gwfbc
            feature=last(fn(*[tuple(p) for p in hp['points']]))
            self.roots['hydraulic:'+hp['id']]=str(feature.Name)
        for region in c['water_regions']:
            pts=[tuple(p) for p in region['polygon']]
            g.line(*(pts+[pts[0]]))
        g.gotowater()
        levels=[('GLOBAL',c['project']['initial_water'])]+[(r['id'],r['points']) for r in c['water_regions']]
        for ident,pts in levels:
            wl=g.waterlevel(*[tuple(p) for p in pts]);self.water_names[ident]=str(wl.Name)
        g.gotostages()
        for st in self.payload['stages']:
            phase=g.InitialPhase if st['id']=='INITIAL' else g.phase(getattr(g,self.phase_names[st['previous_id']]))
            self.phase_names[st['id']]=str(phase.Name)
            g.setproperties(phase,'Identification',st['id'],'Comments','PITBUILDER:'+st['id'])
            if st['id']!='INITIAL':
                g.setproperties(phase,*args(phase_properties(st)))
        self.write_stages()

    # 写入一个对象在指定阶段的属性，同时把请求值按对象名.属性写入 expected。
    # 这只是记录期望，真正成功需由 readback 读取软件当前值并比较。
    def assignment(self,obj,phase,prop,val,expected):
        self.g.set(getattr(obj,prop),phase,val)
        expected[str(obj.Name)+'.'+prop]=val

    # 调用阶段赋材 API，并把实际材料对象名记录为该对象此阶段的期望材料引用。
    def assign_material(self,obj,phase,material,expected):
        self.g.setmaterial(obj,phase,material)
        expected[str(obj.Name)+'.Material']=str(material.Name)

    # 逐阶段显式写完整的土体、结构、界面及水力状态，不依赖软件隐式继承。
    # 先停用可变结构/水设施，再按编译结果启用当前对象，防止旧方案在后续阶段残留。
    # 只对已经停用的开挖空区使用 Dry；保留土体使用全局或局部水位，维持其多孔介质身份。
    def write_stages(self):
        g=self.g;c=self.c
        # Build geometry caches only after final cut generation; never reuse pre-cut references.
        # 全部几何切线生成并进入阶段模式后，才缓存最终土簇包围盒。
        # 若未来增加再次生成几何的流程，必须重新建立这里的缓存和映射，不能沿用旧代理。
        soil_boxes={str(o.Name):bbox(o) for o in g.Soils}
        self.audit.append({'soil_bounds':soil_boxes,'roots':self.roots,'waterlevels':self.water_names})
        for st in self.payload['stages']:
            print('Writing phase '+st['id'],flush=True)
            p=getattr(g,self.phase_names[st['id']]);h=self.payload['hydraulics'][st['id']];e={}
            e['@TimeInterval']=st['duration_days'];e['@DeformCalcType']=1 if st['id']=='INITIAL' else CALCULATION_TYPES[st['calculation_type']]
            e['@PorePresCalcType']=PORE_TYPES[st['pore_pressure_type']]
            if st['calculation_type']=='Safety':
                # PLAXIS disallows editing model conditions in a Safety phase.
                # Verify the inherited construction state instead of rewriting it.
                inherited=copy.deepcopy(self.expected[st['previous_id']]);inherited.update(e)
                inherited['@PreviousPhase']=self.phase_names[st['previous_id']]
                self.expected[st['id']]=inherited
                continue
            g.setglobalwaterlevel(getattr(g,self.water_names['GLOBAL']),p)
            e['Water.GlobalWaterLevel']=self.water_names['GLOBAL']
            for prop,val in h['flow_boundaries'].items():self.assignment(g.GroundwaterFlow,p,prop,val,e)
            self.assignment(g.Precipitation,p,'Active',False,e)
            for obj in g.Soils:
                active=soil_state(soil_boxes[str(obj.Name)],self.left,self.right,st['excavation_y'])
                self.assignment(obj,p,'Active',active,e)
                lids=[lid for lid in c['layer_materials'] if str(obj.Name).startswith(self.roots['layer:'+lid]+'_')]
                if len(lids)!=1:raise RuntimeError('切分后的逻辑层位映射不唯一: '+str(obj.Name))
                self.assign_material(obj,p,self.materials[c['layer_materials'][lids[0]]],e)
                wc=obj.WaterConditions
                # 仍激活的土体继续使用水位条件；下面的 Dry 分支仅针对已停用的开挖空区。
                # 不能靠把保留土体设成 Dry 来模拟降低水头，那会改变土体参与水过程的方式。
                if active:
                    self.assignment(wc,p,'Conditions','Global level',e)
                else:self.assignment(wc,p,'Conditions','Dry',e)
                # Explicit custom water regions are conservatively classified by full bounding-box containment.
                if active and c['water_regions']:
                    from .region_math import containing_region
                    rid=containing_region(soil_boxes[str(obj.Name)],c['water_regions'])
                    if rid:
                        g.setwaterlevel(obj,p,getattr(g,self.water_names[rid]));e[str(wc.Name)+'.Level']=self.water_names[rid]
                        e[str(wc.Name)+'.Conditions']='Custom level'
            for obj in g.Plates:self.assignment(obj,p,'Active',False,e)
            for obj in g.NodeToNodeAnchors:self.assignment(obj,p,'Active',False,e)
            for obj in g.Interfaces:
                self.assignment(obj,p,'Active',False,e);self.assignment(obj,p,'ActiveInFlow',False,e)
            for w in c['walls']:
                for obj in children(g.Plates,self.roots['wall:'+w['id']]):self.assignment(obj,p,'Active',st['walls_active'],e)
                for side in ['pos','neg']:
                    for obj in children(g.Interfaces,self.roots[side+':'+w['id']]):
                        active=st['walls_active'];self.assignment(obj,p,'Active',active,e);self.assignment(obj,p,'ActiveInFlow',active,e)
                        # 本机接口的 Permeable 与 ActiveInFlow 存在联动：Permeable=False 会使界面参与流动。
                        # 因此未安装墙段取 Permeable=True，已安装墙段由显式界面材料控制穿墙水力性质。
                        self.assignment(obj,p,'Permeable',not active,e)
                        bb=bbox(obj)
                        segment=segment_layer(self.interface_segments[w['id']],bb[1],bb[3])
                        material=self.materials[wall_material_key('BLOCK',w['id'],segment['layer_id'])]
                        self.audit.append({'phase':st['id'],'wall':w['id'],'side':side,'interface':str(obj.Name),'layer_id':segment['layer_id'],'source_material':segment['material_id'],'bounds':bb})
                        for leak in h['leaks']:
                            if leak['wall']==w['id'] and bb[1]>=leak['bottom']-EPS and bb[3]<=leak['top']+EPS:
                                outside=(side=='pos')==self.wall_positive_outside[w['id']]
                                material=self.materials[wall_material_key('LEAK',w['id'],segment['layer_id'],leak['id']) if outside else wall_material_key('OPEN',w['id'],segment['layer_id'])]
                        self.assign_material(obj,p,material,e)
            for struct in c['structures']:
                active=struct['id'] in st['active_structure_ids'];coll=g.NodeToNodeAnchors if struct['kind']=='anchor' else g.Plates
                for obj in children(coll,self.roots['structure:'+struct['id']]):
                    self.assignment(obj,p,'Active',active,e)
                    if struct['kind']=='anchor':
                        # 仅首次安装且明确给出非零预应力时调整力值。
                        # 后续开挖/停歇显式写 AdjustPrestress=False，避免每一期都把支撑重新张拉回初始力。
                        install=active and struct['id'] in st['new_structure_ids'] and bool(struct.get('prestress',0))
                        self.assignment(obj,p,'AdjustPrestress',install,e)
                        if install:self.assignment(obj,p,'PrestressForce',struct['prestress'],e)
                if struct['kind']=='slab':
                    for side in ['slabpos','slabneg']:
                        for obj in children(g.Interfaces,self.roots[side+':'+struct['id']]):
                            self.assignment(obj,p,'Active',active,e);self.assignment(obj,p,'ActiveInFlow',active,e);self.assignment(obj,p,'Permeable',not active,e)
                            bb=bbox(obj);line=obj.Parent
                            positive_above=float(line.Second.x.value)>float(line.First.x.value)
                            layer_id=horizontal_adjacent_layer(c,bb[0],bb[2],(bb[1]+bb[3])/2,(side=='slabpos')==positive_above)
                            self.assign_material(obj,p,self.materials['IF-SLAB-'+layer_id],e)
            for obj in g.GroundwaterFlowBCs:self.assignment(obj,p,'Active',False,e)
            for obj in g.Drains:self.assignment(obj,p,'Active',False,e)
            hp=h['boundary']
            if hp:
                coll=g.Drains if hp['mode']=='drain' else g.GroundwaterFlowBCs
                selected=children(coll,self.roots['hydraulic:'+hp['id']])
                if not selected:raise RuntimeError('排水设施切分映射缺失: '+hp['id'])
                for obj in selected:
                    self.assignment(obj,p,'Active',True,e)
                    self.assignment(obj,p,'Behaviour','Normal' if hp['mode']=='drain' else 'Head',e)
                    self.assignment(obj,p,'h' if hp['mode']=='drain' else 'Href',hp['head'],e)
                if hp.get('seepage') and st['excavation_y'] in self.payload['geometry']['excavation_cuts']:
                    for obj in children(g.GroundwaterFlowBCs,self.roots['surface:'+str(st['excavation_y'])]):
                        self.assignment(obj,p,'Active',True,e);self.assignment(obj,p,'Behaviour','Seepage',e)
            self.expected[st['id']]=e

    # 读取软件当前各阶段的实际属性、材料参数和水位引用，返回期望/实际/差异。
    # 阶段枚举数值与请求文字统一后再比较，对象引用以真实名称比较；材料从 echo 再次解析。
    # 保存前后均可复用，同一对象名存在不代表其状态一定正确。
    def readback(self):
        g=self.g;actual={};enums={'BoundaryXMin':{'Open':1,'Closed':0},'BoundaryXMax':{'Open':1,'Closed':0},'BoundaryYMin':{'Open':1,'Closed':0},'BoundaryYMax':{'Open':1,'Closed':0},'Conditions':{'Global level':0,'Custom level':1,'Dry':5},'Behaviour':{'Head':2,'Seepage':0,'Normal':0}}
        expected=copy.deepcopy(self.expected)
        for sid,want in self.expected.items():
            p=getattr(g,self.phase_names[sid]);row={}
            # Safety has no editable staged model conditions: its getters return
            # None. Resolve its actual native predecessor for construction state,
            # while checking the predecessor reference and phase settings here.
            model_phase=p;visited=set()
            while model_phase.DeformCalcType.value==7:
                name=str(model_phase.Name)
                if name in visited:raise RuntimeError('安全分析前序阶段出现循环')
                visited.add(name);model_phase=getattr(g,str(model_phase.PreviousPhase.Name))
            for key,v in want.items():
                if key=='@PreviousPhase':raw=str(p.PreviousPhase.Name)
                elif key.startswith('@'):raw=getattr(p,key[1:]).value
                else:
                    name,prop=key.rsplit('.',1);obj=getattr(g,name);raw=getattr(obj,prop)[model_phase]
                    if prop in ['Material','Level','GlobalWaterLevel']:raw=str(raw.Name) if raw is not None else None
                    else:raw=raw.value if raw is not None else None
                    if prop in enums and isinstance(v,str):expected[sid][key]=enums[prop][v]
                row[key]=raw
            actual[sid]=row
        differences=compare_state(expected,actual)
        material_checks={}
        for name,props in self.material_expected.items():
            echo=g.echo(getattr(g,name));got={k:material_value(echo,k,v) for k,v in props.items()}
            material_checks[name]={'expected':props,'actual':got}
            differences.extend(compare_state(props,got,'materials.'+name))
        result={'expected':expected,'actual':actual,'differences':differences}
        result['materials']=material_checks
        return result

# 原生建模事务入口：拒绝覆盖 → 建模 → 回读 → 保存 → 重开 → 再回读。
# payload 必须已经离线编译；可选 session 仅供已验证归属的集成测试，生产入口自动新建会话。
# 任何差异均抛错并保留证据；显式网格检查后还要重开核对，始终没有 calculate 调用。
def build_project(config,output,executable,report_dir,payload=None,session=None):
    output=Path(output).resolve()
    if output.exists() or Path(str(output)+'dat').exists():raise ValueError('目标工程已存在，拒绝覆盖')
    if payload is None:raise ValueError('缺少离线编译后的建模计划')
    s,g,_=launch_owned(executable) if session is None else (*session,None)
    writer=NativeBuilder(s,g,config,payload,report_dir)
    writer.create();before=writer.readback()
    report_dir=Path(report_dir)
    (report_dir/'native_before_save.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
    (report_dir/'native_mapping.json').write_text(json.dumps(writer.audit,ensure_ascii=False,indent=2),encoding='utf-8')
    if before['differences']:raise RuntimeError('软件回读与请求不同，查看 native_before_save.json')
    # 保存后重新打开同一新工程，再从软件当前状态回读，核对磁盘实际保留值。
    # 这与只检查保存命令返回值不同；任何阶段或材料差异都会阻止成功状态输出。
    g.save(str(output));s.open(str(output));g.gotostages();after=writer.readback()
    if after['differences']:raise RuntimeError('保存重开后设置不一致')
    if not Path(output).is_file() or not Path(str(output)+'dat').is_dir():raise RuntimeError('未生成完整工程')
    result={'status':'model_saved_verified','application':s.server_full_name,'project':str(output),
            'calculation_requested':False,'mesh_requested':False,'phase_count':len(writer.phase_names),
            'readback_before_save':not before['differences'],'readback_after_reopen':not after['differences'],
            'verified_phase_properties':sum(len(x) for x in after['actual'].values())}
    if payload.get('mesh_check'):
        g.gotomesh();result['mesh_feedback']=str(g.mesh(0.06));g.save(str(output))
        result['mesh_requested']=True
        s.open(str(output));g.gotostages();after=writer.readback()
        if after['differences']:raise RuntimeError('网格检查后保存重开，阶段/材料设置发生变化')
    (report_dir/'native_after_reopen.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
