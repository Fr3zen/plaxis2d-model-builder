# 【模块中文说明】
# 离线编译地层范围、围护位置和全部未来开挖切线。
# 地层采用旧生成器的验证结果，WKT 用于跨进程传递几何，配置中保留逻辑层位和材料编号。
# classify_cut_objects 通过面积包含关系核对观测土区，不按中心点或固定软件对象序号分配材料。
# 本模块不向 PLAXIS 写入对象；真实写入及切分映射在 plaxis_adapter 中完成。
# 
from shapely.geometry import Polygon,box
from .legacy import build_model
from .interfaces import wall_segments

# 根据配置及完整阶段提取左右墙、所有开挖标高和逻辑层多边形。
# 相同开挖标高去重，土层以 WKT 序列化，便于外层与匹配 PLAXIS Python 之间传递。
def plan_geometry(config,stages):
    holes,domain,regions,report=build_model(config['geology'])
    left,right=sorted(w['x'] for w in config['walls'])
    cuts=sorted(set(s['excavation_y'] for s in stages if s['operation']=='excavate'))
    return {'left':left,'right':right,'bounds':config['project']['bounds'],
            'excavation_cuts':cuts,'layer_materials':config['layer_materials'],
            'layers':{r['layer']['id']:r['polygon'].wkt for r in regions},'wall_interfaces':{w['id']:wall_segments(config,w) for w in config['walls']},'validation':report}

# 对观测到的实际土区检查几何有效性、原层包含关系及是否完全位于坑内。
# 返回真实对象名到层位/材料/坑内外属性的映射；跨越坑边界的对象必须先切分，不能靠质心猜测。
def classify_cut_objects(plan,observations):
    from shapely import wkt
    result={};pit=box(plan['left'],plan['bounds'][1],plan['right'],plan['bounds'][3])
    for row in observations:
        poly=Polygon(row['polygon'])
        if poly.is_empty or not poly.is_valid or poly.area<=1e-10:raise ValueError('无效土区几何: '+row['name'])
        lid=row['layer_id'];layer=wkt.loads(plan['layers'][lid]);tol=max(poly.area,1)*1e-8
        if poly.difference(layer).area>tol:raise ValueError('切分土区与原生层位不匹配')
        inside=poly.intersection(pit).area
        if tol<inside<poly.area-tol:raise ValueError('土区跨越坑内外，不能猜测分类')
        result[row['name']]={'layer_id':lid,'material_id':plan['layer_materials'][lid],
                             'inside_pit':inside>=poly.area-tol,'bounds':list(poly.bounds)}
    return result
