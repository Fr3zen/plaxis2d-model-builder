"""Coherent reader fixture independent of the user's editable workbook values."""
import json
from pathlib import Path
from pitbuilder.workbook import SHEETS,HEADER_LABELS

def workbook_cells():
    c=json.loads((Path(__file__).resolve().parents[1]/'examples/demo.json').read_text(encoding='utf-8'))
    out={}
    def table(name,headers,rows):
        values=[[HEADER_LABELS.get(name,{}).get(h,h) for h in headers]]+rows
        out[name]={(r+1,k+1):(value,'fixture') for r,row in enumerate(values) for k,value in enumerate(row) if value is not None}
    p=c['project']
    table('工程',['parameter','value'],[['name',p['name']]]+[[k,v] for k,v in zip(['xmin','ymin','xmax','ymax'],p['bounds'])]+[['start_y',p['start_y']]]+list(map(list,p['flow_boundaries'].items())))
    table('钻孔数据',['钻孔编号','沿剖面距离 x（m）','孔口标高（m）']+[l['name']+'层底标高（m）' for l in c['geology']['layers']],[[h['id'],h['x'],h['ground']]+h['bottoms'] for h in c['geology']['boreholes']])
    table('地层材料',['layer_id','material_id'],list(map(list,c['layer_materials'].items())))
    for key in ['materials','walls','structures','stages','hydraulic_plans','leaks']:
        headers=list(dict.fromkeys(k for row in c[key] for k in row))
        if not headers:headers=['id']
        rows=[[json.dumps(row[h]) if isinstance(row.get(h),(dict,list)) else row.get(h) for h in headers] for row in c[key]]
        table(SHEETS[key],headers,rows)
    table('初始水条件',['region_id','x_m','head_m','polygon'],[['GLOBAL',x,y,None] for x,y in p['initial_water']])
    return out
