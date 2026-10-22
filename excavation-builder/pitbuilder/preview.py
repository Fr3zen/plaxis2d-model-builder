# 【模块中文说明】
# 从离线计划输出每阶段 PNG、HTML 和阶段设置 JSON。
# 图中的水位线、降水线及漏水段都是输入条件，不是计算所得孔压、流量或位移。
# 使用 Agg 后端可在无图形桌面时出图；HTML 仅引用同目录图像。
# 当前预览主要表达地层、结构及当期水力控制，不替代软件对象回读报告。
# 
import html
import json
from .phase_settings import CALCULATION_LABELS
from pathlib import Path

# 把完整阶段状态绘成每期剖面，返回图片路径、HTML 路径及非计算结果标记。
# 墙、已安装支撑、当期水力设施和漏水段按各阶段状态绘制，输出目录由调用者事先保护。
def write_preview(config,geometry_plan,stages,hydraulics,output_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon,Rectangle
    from .legacy import build_model
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    holes,domain,regions,_=build_model(config['geology']);images=[];rows=[]
    for st in stages:
        fig,ax=plt.subplots(figsize=(11,5))
        for r in regions:
            geom=r['polygon']
            for poly in ([geom] if geom.geom_type=='Polygon' else geom.geoms):
                if not poly.is_empty:ax.add_patch(Polygon(list(poly.exterior.coords),facecolor=r['layer']['color'],edgecolor='#777777',linewidth=.5))
        x1,x2=geometry_plan['left'],geometry_plan['right'];y=st['excavation_y'];ymax=config['project']['bounds'][3]
        if st['operation']!='initial':ax.add_patch(Rectangle((x1,y),x2-x1,ymax-y,color='white',zorder=3))
        for w in config['walls']:
            ax.plot([w['x']]*2,[w['top'],w['bottom']],color='#263d50' if st['walls_active'] else '#999999',linewidth=3,zorder=4)
        for obj in config['structures']:
            if obj['id'] in st['active_structure_ids']:ax.plot([x1,x2],[obj['y']]*2,color='#7a2e87',linewidth=3,zorder=4)
        h=hydraulics[st['id']];hp=h['boundary']
        ax.plot(*zip(*config['project']['initial_water']),color='#25869b',linestyle='--',label='初始/外部参考水位')
        if hp:
            ax.plot(*zip(*hp['points']),color='#1265ac',linewidth=2,label='等效控制线' if hp['mode']=='equivalent_head' else '排水线',zorder=6)
            ax.text(x1,hp['points'][0][1]-1,'目标总水头 h={} m'.format(hp['head']),color='#1265ac',zorder=7)
        for leak in h['leaks']:
            w=next(w for w in config['walls'] if w['id']==leak['wall'])
            ax.plot([w['x']]*2,[leak['top'],leak['bottom']],color='#c33d27',linewidth=6,zorder=7)
        xmin,ymin,xmax,ymax=config['project']['bounds'];ax.set_xlim(xmin,xmax);ax.set_ylim(ymin,ymax+2)
        ax.set_xlabel('沿剖面距离 x / m');ax.set_ylabel('标高 y / m')
        calc=CALCULATION_LABELS.get(st['calculation_type'],'K0初始应力')
        ax.set_title('{} | {} | {} | 输入条件预览（非计算结果）'.format(st['id'],st['operation'],calc))
        ax.legend(loc='lower left');ax.grid(alpha=.15);fig.tight_layout()
        name=out/('phase_{:03d}.png'.format(len(images)));fig.savefig(str(name),dpi=130);plt.close(fig);images.append(str(name))
        rows.append('<h2>{}</h2><p>操作：{}；计算类型：{}；开挖面：{} m；阶段历时：{} day；孔压方式：{}</p><img src="{}">'.format(html.escape(st['id']),html.escape(st['operation']),calc,y,st['duration_days'],html.escape(st['pore_pressure_type']),name.name))
    interfaces='<h2>墙—土界面分层赋材</h2>'+''.join('<p>{}：{}</p>'.format(html.escape(wall),'; '.join('{}～{} m → {}'.format(s['top'],s['bottom'],html.escape(s['material_id'])) for s in segments)) for wall,segments in geometry_plan.get('wall_interfaces',{}).items())
    (out/'preview.html').write_text('<!doctype html><meta charset="utf-8"><title>基坑输入预览</title><style>body{font:16px sans-serif;max-width:1100px;margin:30px auto}img{max-width:100%}</style><h1>基坑分期输入条件预览</h1><p>演示或输入条件的可视化，不是计算所得水位、孔压或变形。红色墙段表示局部透水。</p>'+interfaces+''.join(rows),encoding='utf-8')
    (out/'phase_settings.json').write_text(json.dumps({'stages':stages,'hydraulics':hydraulics},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'phase_images':images,'calculation_results':False,'html':str(out/'preview.html')}
