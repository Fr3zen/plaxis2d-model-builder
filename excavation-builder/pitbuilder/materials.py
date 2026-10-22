# 【模块中文说明】
# 材料输入合同及本构参数完整性检查。
# soil、plate、anchor 分别要求各自的必要参数；土体水平与竖向渗透系数保持独立。
# UDSM 需要可用 DLL、模型名称及完整连续的 User1…UserN，不允许用默认参数悄悄补齐缺项。
# 目前水力分类只接受明确的 Standard；自定义持水/相对渗透曲线尚需额外的已验证合同。
# 
from pathlib import Path
import math

# 逐材料核对类别对应的必要字段，并返回材料请求列表。
# UDSM 用完整连续编号集合检查参数向量，DLL 文件名需与路径一致；并不由文件名推断参数物理意义。
# 只接受当前已验证的水力分类，水平/竖向渗透系数分别检查，不强制各向同性。
def material_requests(config):
    out=[]
    for m in config['materials']:
        p=m['properties'];kind=m['kind']
        required={'soil':['SoilModel','DrainageType','gammaUnsat','gammaSat','PermHorizontalPrimary','PermVertical','GroundwaterClassificationType'],
                  'plate':['MaterialType','EA1','EI','w','StructNu'],'anchor':['MaterialType','EA','LSpacing']}
        if kind not in required:raise ValueError('未知材料类型: '+kind)
        missing=[k for k in required[kind] if k not in p]
        if missing:raise ValueError('材料 {} 缺参数 {}'.format(m['id'],missing))
        if kind=='soil':
            model=p['SoilModel']
            if model in ['Mohr-Coulomb',2]:
                if any(k not in p for k in ['ERef','nu','cref','phi']):raise ValueError('Mohr-Coulomb 材料缺少有效应力参数')
            elif model in ['User-defined',100]:
                if not Path(str(m.get('dll_path',''))).is_file():
                    raise ValueError('UDSM 必须提供可用 DLL 和完整已验证参数映射，不允许替换本构')
                if not p.get('DllFile') or not p.get('ModelInDll') or not any(k.startswith('User') for k in p):
                    raise ValueError('UDSM 缺 DLL/模型/用户参数')
                count=m.get('udsm_parameter_count')
                if not isinstance(count,(int,float)) or isinstance(count,bool) or not math.isfinite(count) or count<1 or count!=int(count):raise ValueError('UDSM 必须声明模型的完整参数个数')
                # Excel 读取器把数字 17 解析为 17.0；通过有限、正值和整数性检查后，只在局部转整型用于构造 User 编号集合。
                count=int(count)
                import re
                supplied={k for k in p if re.fullmatch(r'User\d+',k)}
                if supplied!={'User'+str(i) for i in range(1,count+1)}:raise ValueError('UDSM 参数向量缺项或编号不连续')
                if Path(m['dll_path']).name.lower()!=str(p['DllFile']).lower():raise ValueError('DLL 路径与材料选用的DLL名称不一致')
            elif not m.get('parameter_contract_verified'):
                raise ValueError('该本构尚无已验证参数合同: '+str(model))
            for k in ['PermHorizontalPrimary','PermVertical']:
                if not isinstance(p[k],(int,float)) or isinstance(p[k],bool) or not math.isfinite(p[k]) or p[k]<=0:
                    raise ValueError('材料渗透系数必须为有效正数: '+m['id'])
            # 自定义持水或相对渗透模型若缺少完整参数，软件可能采用未声明默认值。
            # 当前明确拒绝尚未验证的合同，而不是仅比对已提供字段后就宣称水力材料完整。
            if p['GroundwaterClassificationType']!='Standard':
                raise ValueError('当前仅支持完整标准水力分类；自定义持水及相对渗透曲线尚无已验证参数合同')
            if 'GroundwaterSoilClassStandard' not in p:
                raise ValueError('需明确水力分类，不能按层名猜测')
        out.append(dict(m))
    return out

# 复用嵌套状态比较器比较材料请求和回读值；返回差异列表，空列表才表示一致。
def compare_material(expected,actual):
    from .verify import compare_state
    return compare_state(expected,actual)
