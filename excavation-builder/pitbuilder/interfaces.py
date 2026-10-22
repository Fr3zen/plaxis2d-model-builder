"""Resolve complete interface segments against piecewise-linear borehole layers."""
EPS=1e-7

def levels_at(config,x):
    holes=sorted(config['geology']['boreholes'],key=lambda h:h['x'])
    if x<holes[0]['x']-EPS or x>holes[-1]['x']+EPS:raise ValueError('界面超出钻孔覆盖范围')
    for a,b in zip(holes,holes[1:]):
        if a['x']-EPS<=x<=b['x']+EPS:
            t=(x-a['x'])/(b['x']-a['x'])
            return [u+(v-u)*t for u,v in zip([a['ground']]+a['bottoms'],[b['ground']]+b['bottoms'])]
    raise ValueError('无法插值界面处的地层标高')

def wall_segments(config,wall):
    levels=levels_at(config,wall['x']);result=[]
    if wall['top']>levels[0]+EPS or wall['bottom']<levels[-1]-EPS:
        raise ValueError('墙体自动界面超出有相邻土层的范围: '+wall['id'])
    for i,layer in enumerate(config['geology']['layers']):
        top=min(wall['top'],levels[i]);bottom=max(wall['bottom'],levels[i+1])
        if top-bottom<=EPS:continue
        requested=wall.get('interface_material','AUTO')
        material=config['layer_materials'][layer['id']] if requested in ['AUTO','自动','按相邻土层',None,''] else requested
        result.append({'layer_id':layer['id'],'material_id':material,'top':top,'bottom':bottom})
    if not result:raise ValueError('墙体没有可识别的土层接触段: '+wall['id'])
    return result

def segment_layer(segments,bottom,top):
    candidates=[s for s in segments if top<=s['top']+EPS and bottom>=s['bottom']-EPS and top-bottom>EPS]
    if len(candidates)!=1:raise ValueError('界面子段跨越土层或归属不唯一，必须按地层交点切分')
    return candidates[0]

def horizontal_adjacent_layer(config,xmin,xmax,y,above):
    # Within each borehole span, layer boundaries are linear. Checking both
    # ends of every span proves containment; no midpoint-only assignment.
    breaks=[xmin]+[h['x'] for h in config['geology']['boreholes'] if xmin<h['x']<xmax]+[xmax]
    breaks=sorted(set(breaks));found=set();yy=y+(1 if above else -1)*EPS*10
    for x1,x2 in zip(breaks,breaks[1:]):
        for t in [1e-6,1-1e-6]:
            levels=levels_at(config,x1+(x2-x1)*t)
            candidates=[l['id'] for i,l in enumerate(config['geology']['layers']) if levels[i+1]<yy<levels[i]]
            if len(candidates)!=1:raise ValueError('水平界面没有明确的相邻土层')
            found.add(candidates[0])
    if len(found)!=1:raise ValueError('水平界面子段跨越土层，需进一步切分')
    return next(iter(found))

def wall_material_key(mode,wall_id,layer_id,leak_id=None):
    return 'IF-'+mode+'-'+wall_id+'-'+layer_id+('-'+leak_id if leak_id else '')
