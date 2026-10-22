"""PLAXIS 2024.1 four-type stage contract; enums confirmed by native readback."""
CALCULATION_TYPES={'Plastic':4,'Consolidation':6,'Safety':7,'Fully coupled flow-deformation':10}
CALCULATION_LABELS={'Plastic':'塑性','Consolidation':'固结','Safety':'安全分析','Fully coupled flow-deformation':'完全耦合渗流—变形'}
PORE_TYPES={'Phreatic':0,'Use pressures from previous phase':1,'Steady state groundwater flow':2,'Fully coupled flow-deformation':4}
CALCULATION_ALIASES={label:key for key,label in CALCULATION_LABELS.items()}
CALCULATION_ALIASES.update({'安全':'Safety','完全耦合':'Fully coupled flow-deformation','完全耦合渗流-变形':'Fully coupled flow-deformation'})
PORE_ALIASES={'潜水位生成':'Phreatic','沿用前序孔压':'Use pressures from previous phase','稳态地下水流':'Steady state groundwater flow','完全耦合渗流—变形':'Fully coupled flow-deformation'}

def calculation_type(value):
    value=CALCULATION_ALIASES.get(value,value)
    if value not in CALCULATION_TYPES:raise ValueError('计算类型仅支持塑性、固结、安全分析、完全耦合渗流—变形')
    return value

def pore_pressure_type(kind,value=None):
    if value in [None,'','自动']:
        return {'Safety':'Use pressures from previous phase','Fully coupled flow-deformation':'Fully coupled flow-deformation'}.get(kind,'Steady state groundwater flow')
    value=PORE_ALIASES.get(value,value)
    allowed=['Phreatic','Use pressures from previous phase','Steady state groundwater flow']
    if kind=='Safety':allowed=['Use pressures from previous phase']
    if kind=='Fully coupled flow-deformation':allowed=['Fully coupled flow-deformation']
    if value not in allowed:raise ValueError('计算类型 {} 不允许孔压生成方式 {}'.format(kind,value))
    return value

def phase_properties(stage):
    return {'DeformCalcType':stage['calculation_type'],'TimeInterval':stage['duration_days'],'PorePresCalcType':stage['pore_pressure_type']}
