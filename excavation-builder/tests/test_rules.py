# 【模块中文说明】
# 离线单元测试：构造最小完整配置，覆盖层位、材料、UDSM、阶段依赖、时长和预应力安装规则。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
import copy
import json
from pathlib import Path
import unittest

# 返回每个测试独立使用的最小完整工程字典。
# 包含两层土、双墙、单道支撑、先降水后开挖及有限墙阻力，便于单独改变一个条件。
def sample():
    return {
        'schema_version': 1,
        'project': {'name': 'demo', 'bounds': [0,-20,40,0], 'start_y': 0,
                    'initial_water': [[0,-1],[40,-1]],
                    'flow_boundaries': {'BoundaryXMin':'Open','BoundaryXMax':'Open','BoundaryYMin':'Closed','BoundaryYMax':'Open'}},
        'geology': {'name':'demo','units':'m','layers':[{'id':'L1','name':'clay','color':'#aa9988'},{'id':'L2','name':'sand','color':'#ccbbaa'}],
                    'boreholes':[{'id':'B1','x':0,'ground':0,'bottoms':[-5,-20]}, {'id':'B2','x':40,'ground':0,'bottoms':[-5,-20]}]},
        'layer_materials': {'L1':'SOIL','L2':'SOIL'},
        'materials': [{'id':'SOIL','kind':'soil','properties':{'SoilModel':'Mohr-Coulomb','DrainageType':'Drained','gammaUnsat':18,'gammaSat':20,'ERef':20000,'nu':0.3,'cref':10,'phi':28,'PermHorizontalPrimary':0.01,'PermVertical':0.005,'GroundwaterClassificationType':'Standard','GroundwaterSoilClassStandard':'Fine','GwUseDefaults':False}},
                      {'id':'WALL','kind':'plate','properties':{'MaterialType':'Elastic','EA1':10000000,'EI':80000,'w':5,'StructNu':0.2}},
                      {'id':'STRUT','kind':'anchor','properties':{'MaterialType':'Elastic','EA':1000000,'LSpacing':3}}],
        'walls': [{'id':'LEFT','x':10,'top':0,'bottom':-12,'material':'WALL','interface_material':'SOIL'}, {'id':'RIGHT','x':30,'top':0,'bottom':-12,'material':'WALL','interface_material':'SOIL'}],
        'structures':[{'id':'S1','kind':'anchor','y':-1,'material':'STRUT','prestress':0}],
        'water_regions': [],
        'hydraulic_plans':[{'id':'H1','mode':'equivalent_head','points':[[10,-3],[30,-3]],'head':-3,'seepage':True}],
        'leaks':[{'id':'LEAK','wall':'RIGHT','top':-1,'bottom':-2,'first':'D1','last':'E1','mode':'resistance','resistance_days':50}],
        'stages':[{'id':'W1','previous':'INITIAL','operation':'walls','duration_days':0.1},
                  {'id':'D1','previous':'W1','operation':'dewater','duration_days':0.2,'hydraulic_plan':'H1'},
                  {'id':'E1','previous':'D1','operation':'excavate','excavation_y':-2,'duration_days':1},
                  {'id':'S1INSTALL','previous':'E1','operation':'support','structure_ids':['S1'],'duration_days':0.1}]
    }

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class InputContract(unittest.TestCase):
    # 测试辅助入口：以当前目录作为相对文件基准，调用真实 schema 校验器，避免在测试中复制验证逻辑。
    def validate(self,c):
        from pitbuilder.schema import validate_config
        return validate_config(c,Path('.'))
    # 令一孔首层厚度为 0，断言校验后仍保留该逻辑层位编号。
    def test_zero_thickness_keeps_identity(self):
        c=sample();c['geology']['boreholes'][0]['bottoms'][0]=0
        self.assertEqual(self.validate(c)['geology']['layers'][0]['id'],'L1')
    # 逐一构造层底倒置、未知材料、NaN、阶段环及漏水重叠，确保每种错误均被明确拒绝。
    def test_reject_inverted_and_missing_material(self):
        for change in ['layer','material','nan','cycle','overlap']:
            c=sample()
            if change=='layer':c['geology']['boreholes'][0]['bottoms']=[-21,-20]
            if change=='material':c['walls'][0]['material']='NO'
            if change=='nan':c['materials'][0]['properties']['PermVertical']=float('nan')
            if change=='cycle':c['stages'][0]['previous']='E1'
            if change=='overlap':c['leaks'].append(dict(c['leaks'][0],id='OTHER'))
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(c)
    # 保持水平与竖向渗透系数不同，断言输入校验不擅自改成各向同性。
    def test_permeabilities_not_forced_equal(self):
        c=self.validate(sample());self.assertEqual(c['materials'][0]['properties']['PermVertical'],0.005)
    # 改为未建立完整参数合同的用户水力分类，断言不会静默使用软件默认曲线。
    def test_unsupported_retention_contract_rejected(self):
        c=sample();c['materials'][0]['properties']['GroundwaterClassificationType']='User-defined'
        with self.assertRaises(ValueError):self.validate(c)
    # 把普通施工阶段命名为 INITIAL，断言不会覆盖初始状态或破坏阶段映射。
    def test_reserved_initial_phase_rejected(self):
        c=sample();c['stages'][-1]['id']='INITIAL'
        with self.assertRaises(ValueError):self.validate(c)
    # 要求用户本构但不提供必要 DLL/参数，断言失败，不自动替换为内置土模型。
    def test_udsm_never_falls_back(self):
        c=sample();c['materials'][0]['properties']['SoilModel']='User-defined'
        with self.assertRaises(ValueError):self.validate(c)
    # 去掉结构材料的 MaterialType，断言在连接软件之前就指出缺项。
    def test_structural_material_type_required(self):
        c=sample();c['materials'][1]['properties'].pop('MaterialType')
        with self.assertRaises(ValueError):self.validate(c)
    # 让墙引用土材料，断言几何特征与材料类别不匹配会报错。
    def test_material_kind_must_match_feature(self):
        c=sample();c['walls'][0]['material']='SOIL'
        with self.assertRaises(ValueError):self.validate(c)
    # 构造重叠局部水分区，断言不允许同一土区存在多个初始水位来源。
    def test_overlapping_water_regions_rejected(self):
        c=sample();reg={'id':'A','polygon':[[0,-10],[5,-10],[5,0],[0,0]],'points':[[0,-1],[5,-1]]}
        c['water_regions']=[reg,dict(reg,id='B')]
        with self.assertRaises(ValueError):self.validate(c)
    # 把规定水头控制线放在同期开挖排水面上，断言同一面不能同时强制 Head 和 Seepage。
    def test_cut_control_on_seepage_surface_rejected(self):
        from pitbuilder.stages import compile_stages
        from pitbuilder.geometry import plan_geometry
        from pitbuilder.hydraulics import compile_hydraulics
        c=sample();c['hydraulic_plans'][0].update(points=[[10,-2],[30,-2]],head=-2)
        st=compile_stages(c)
        with self.assertRaises(ValueError):compile_hydraulics(c,st,plan_geometry(c,st))
    # 水平混凝土梁使用板材料应通过，避免误把所有水平结构都当成锚杆。
    def test_concrete_beam_uses_plate_material(self):
        c=sample();c['structures'][0].update(kind='beam',material='WALL')
        self.assertEqual(self.validate(c)['structures'][0]['kind'],'beam')
    # 声明三参数模型却缺 User2，断言不连续向量会被拒绝。
    def test_udsm_parameter_vector_has_no_gaps(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dll=Path(d)/'model.dll';dll.write_bytes(b'fixture-not-loaded')
            c=sample();m=c['materials'][0]
            m.update(dll_path=str(dll),udsm_verified=True,udsm_parameter_count=3)
            m['properties'].update(SoilModel='User-defined',DllFile='model.dll',ModelInDll='Model',User1=1,User3=3)
            with self.assertRaises(ValueError):self.validate(c)
    # 模拟 Excel 数值 3.0，应按完整整数计数接受；布尔值、非整数、无穷/NaN、零和文字计数都拒绝。
    def test_excel_integral_udsm_count_and_invalid_counts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dll=Path(d)/'model.dll';dll.write_bytes(b'fixture-not-loaded')
            c=sample();m=c['materials'][0]
            m.update(dll_path=str(dll),udsm_parameter_count=3.0)
            m['properties'].update(SoilModel='User-defined',DllFile='model.dll',ModelInDll='Model',User1=1,User2=2,User3=3)
            self.assertEqual(self.validate(c)['materials'][0]['udsm_parameter_count'],3)
            for bad in [True,3.5,float('nan'),float('inf'),0,'3']:
                m['udsm_parameter_count']=bad
                with self.subTest(count=bad),self.assertRaises(ValueError):self.validate(c)

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Stages(unittest.TestCase):
    # 测试辅助入口：调用生产阶段或水力编译器，返回真实完整状态供断言；不建立软件会话。
    def compile(self,c):
        from pitbuilder.stages import compile_stages
        return compile_stages(c)
    def test_explicit_duration_preserved(self):
        c=sample();c['project']['start_y']=2.8;c['stages'][2]['excavation_y']=-1.32;c['stages'][2]['duration_days']=2.5
        states=self.compile(c)
        self.assertEqual(states[3]['duration_days'],2.5)
        self.assertEqual(states[4]['active_structure_ids'],['S1'])
        self.assertEqual(states[4]['hydraulic_plan_id'],'H1')
    def test_removed_speed_input_rejected(self):
        c=sample();c['stages'][2]['speed_m_day']=2
        with self.assertRaises(ValueError):self.compile(c)
    def test_four_calculation_types_and_independent_phase_choice(self):
        choices=['塑性','固结','完全耦合渗流—变形','安全分析']
        c=sample()
        c['stages'][3]['operation']='wait';c['stages'][3].pop('structure_ids')
        for row,choice in zip(c['stages'],choices):row['calculation_type']=choice
        states=self.compile(c)[1:]
        self.assertEqual([s['calculation_type'] for s in states],['Plastic','Consolidation','Fully coupled flow-deformation','Safety'])
        self.assertEqual(states[3]['pore_pressure_type'],'Use pressures from previous phase')
        self.assertEqual(states[2]['pore_pressure_type'],'Fully coupled flow-deformation')
        c['stages'][1].pop('calculation_type')
        self.assertEqual(self.compile(c)[2]['calculation_type'],'Consolidation')
    def test_type_specific_duration_and_invalid_combinations(self):
        for kind in ['Plastic','Safety']:
            c=sample();c['stages'][0].update(calculation_type=kind,duration_days=0)
            if kind=='Safety':c['stages'][0]['operation']='wait'
            self.assertEqual(self.compile(c)[1]['duration_days'],0)
        for change in [{'calculation_type':'Dynamics'},{'calculation_type':'Consolidation','duration_days':0},
                       {'calculation_type':'Fully coupled flow-deformation','duration_days':0},
                       {'calculation_type':'Safety','pore_pressure_type':'Phreatic'},
                       {'calculation_type':'Fully coupled flow-deformation','pore_pressure_type':'Steady state groundwater flow'}]:
            c=sample();c['stages'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.compile(c)
    def test_safety_cannot_change_construction_or_water(self):
        for change in [{'operation':'excavate','excavation_y':-3},{'operation':'wait','hydraulic_plan':'H1'}]:
            c=sample();c['stages'].append(dict(id='SAFE',previous='S1INSTALL',calculation_type='Safety',duration_days=0,**change))
            with self.subTest(change=change),self.assertRaises(ValueError):self.compile(c)
    # 支撑安装标高仍埋在未挖土体中时，断言安装阶段无效。
    def test_support_before_exposure_rejected(self):
        c=sample();c['stages'][3]['previous']='W1'
        with self.assertRaises(ValueError):self.compile(c)
    # 去掉施工起始标高，断言不能默认采用 0 m 改变首层开挖厚度。
    def test_no_default_zero_start(self):
        c=sample();c['project'].pop('start_y')
        with self.assertRaises(ValueError):self.compile(c)
    # 检查首次安装标记只在安装期出现，停歇期为空，而从未装支撑的祖先分出的分支可再次独立安装。
    def test_prestress_installation_tracks_actual_predecessor(self):
        c=sample();c['structures'][0]['prestress']=100
        c['stages'] += [{'id':'WAIT','previous':'S1INSTALL','operation':'wait','duration_days':1},
                        {'id':'BRANCH','previous':'E1','operation':'support','structure_ids':['S1'],'duration_days':1}]
        states={s['id']:s for s in self.compile(c)}
        self.assertEqual(states['S1INSTALL']['new_structure_ids'],['S1'])
        self.assertEqual(states['WAIT']['new_structure_ids'],[])
        self.assertEqual(states['BRANCH']['new_structure_ids'],['S1'])

if __name__=='__main__':unittest.main()
