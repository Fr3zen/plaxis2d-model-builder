# 【模块中文说明】
# 把中文 Excel 模板转换成统一的版本 1 配置。
# workbook_headers.json 保存逐工作表的中英文表头映射；字段内容和编号不做猜测性翻译。
# 材料参数、坐标、多边形及结构编号数组通过 JSON 字段表达，空白可选单元格不写入结果。
# 钻孔表沿用旧读表器；其他输入表组装后统一交 schema.validate_config 验证。
# 
import json
from pathlib import Path
from .legacy import read_xlsx,parse_cells
from .schema import validate_config

SHEETS={'project':'工程','geology':'钻孔数据','layer_materials':'地层材料','materials':'材料',
        'walls':'围护结构','structures':'支撑与垫层','water':'初始水条件','stages':'施工阶段','hydraulic_plans':'水力方案','leaks':'漏水段'}
HEADER_LABELS=json.loads(Path(__file__).with_name('workbook_headers.json').read_text(encoding='utf-8'))

# 把第一行表头及后续数据行转成字典列表，按工作表映射中文名为内部英文键。
# 翻译后再检查重复列，防止同时出现中文/英文同义列而静默覆盖；公式单元格拒绝。
def parse_table(cells,name):
    aliases={label:key for key,label in HEADER_LABELS.get(name,{}).items()}
    if name=='围护结构':aliases['界面材料编号']='interface_material'
    headers={c:aliases.get(v[0],v[0]) for (r,c),v in cells.items() if r==1 and v[0] not in (None,'')}
    if not headers:raise ValueError(name+' 缺表头')
    if len(set(headers.values()))!=len(headers):raise ValueError(name+' 表头重复')
    rows=[]
    for r in range(2,max((r for r,c in cells),default=1)+1):
        row={}
        for c,h in headers.items():
            v,ref=cells.get((r,c),(None,''))
            if isinstance(v,dict):raise ValueError('{}!{} 为公式，请粘贴为值'.format(name,ref))
            if v not in (None,''):row[h]=v
        if row:rows.append(row)
    return rows

# 读取十张输入表并组装版本 1 配置；同一局部水分区按 region_id 分组。
# 钻孔数据走原读表合同，材料与坐标字段按 JSON 解码，最终统一调用 validate_config。
def read_workbook(path):
    path=Path(path)
    tables={k:parse_table(read_xlsx(path,n),n) for k,n in SHEETS.items() if k!='geology'}
    # 只把约定的 JSON 单元格字段解码成数组/字典，其他标量字段保留原值；JSON 格式错误直接指出字段名。
    def unpack(row):
        out=dict(row)
        for k in ['properties','points','structure_ids','polygon']:
            if k in out and isinstance(out[k],str):
                try:out[k]=json.loads(out[k])
                except ValueError:raise ValueError('字段 {} 不是有效 JSON'.format(k))
        return out
    c={k:[unpack(r) for r in tables[k]] for k in ['materials','walls','structures','stages','hydraulic_plans','leaks']}
    # 工程表是纵向的“参数名/参数值”，其他大多数表是一行一对象。
    # 中文只用于表头显示，name/xmin 等参数键仍按模板的内部约定填写。
    p={r['parameter']:r['value'] for r in tables['project']}
    c['schema_version']=1
    c['project']={'name':p['name'],'bounds':[p[k] for k in ['xmin','ymin','xmax','ymax']],
                  'start_y':p['start_y'],'flow_boundaries':{k:p[k] for k in ['BoundaryXMin','BoundaryXMax','BoundaryYMin','BoundaryYMax']}}
    c['project']['initial_water']=[[r['x_m'],r['head_m']] for r in tables['water'] if r['region_id']=='GLOBAL']
    c['water_regions']=[]
    # GLOBAL 行组成全局参考水位；其余编号各自组成局部水位线。
    # 同一分区的空间多边形从该组首行读取，控制点则收集整组所有行。
    groups={}
    for r in tables['water']:
        if r['region_id']!='GLOBAL':groups.setdefault(r['region_id'],[]).append(r)
    for rid,rr in groups.items():
        if not rr[0].get('polygon'):raise ValueError('局部水条件缺空间多边形: '+rid)
        c['water_regions'].append({'id':rid,'polygon':json.loads(rr[0]['polygon']),
                                  'points':[[r['x_m'],r['head_m']] for r in rr]})
    # 钻孔表仍由原解析器给出稳定的 layer_1、layer_2… 编号，地层材料表必须引用相同编号。
    c['geology']=parse_cells(read_xlsx(path,SHEETS['geology']),p['name'])
    # Workbook layer IDs are the stable IDs produced by the existing borehole reader.
    c['layer_materials']={r['layer_id']:r['material_id'] for r in tables['layer_materials']}
    return validate_config(c,path.parent)
