# 【模块中文说明】
# 离线单元测试：验证原生对象映射、已有工程保护、线方向和材料枚举解析，软件启动使用替身拦截。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
import unittest

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class NativeMapping(unittest.TestCase):
    def test_safety_inherits_without_writing_forbidden_model_conditions(self):
        from types import SimpleNamespace
        from pitbuilder.plaxis_adapter import NativeBuilder
        from test_rules import sample
        row={'id':'SAFE','previous_id':'P','calculation_type':'Safety','duration_days':0,'pore_pressure_type':'Use pressures from previous phase'}
        g=SimpleNamespace(Soils=[],SafetyPhase=object())
        writer=NativeBuilder(None,g,sample(),{'stages':[row],'hydraulics':{'SAFE':{}}},'.')
        writer.phase_names={'SAFE':'SafetyPhase','P':'ParentPhase'}
        writer.expected={'P':{'@TimeInterval':1,'@DeformCalcType':4,'@PorePresCalcType':2,'GroundwaterFlow.BoundaryXMin':'Open','Anchor.AdjustPrestress':False}}
        writer.write_stages()
        self.assertEqual(writer.expected['SAFE']['@DeformCalcType'],7)
        self.assertEqual(writer.expected['SAFE']['GroundwaterFlow.BoundaryXMin'],'Open')
    def test_safety_readback_follows_actual_previous_phase(self):
        from types import SimpleNamespace
        from pitbuilder.plaxis_adapter import NativeBuilder
        from test_rules import sample
        parent=SimpleNamespace(Name='ParentPhase',DeformCalcType=SimpleNamespace(value=4))
        reference=SimpleNamespace(Name='ParentPhase',DeformCalcType=SimpleNamespace(value=4))
        safety=SimpleNamespace(Name='SafetyPhase',PreviousPhase=reference,DeformCalcType=SimpleNamespace(value=7))
        class Boundary:
            def __getitem__(self,phase):return SimpleNamespace(value=1) if phase is parent else None
        g=SimpleNamespace(SafetyPhase=safety,ParentPhase=parent,GroundwaterFlow=SimpleNamespace(BoundaryXMin=Boundary()))
        w=NativeBuilder(None,g,sample(),{},'.');w.phase_names={'SAFE':'SafetyPhase'}
        w.expected={'SAFE':{'@DeformCalcType':7,'@PreviousPhase':'ParentPhase','GroundwaterFlow.BoundaryXMin':'Open'}}
        self.assertEqual(w.readback()['differences'],[])
    # 预先放入已有工程，断言直接原生入口先拒绝覆盖，且绝不会启动软件或改变文件内容。
    def test_direct_builder_refuses_existing_project(self):
        from pitbuilder.plaxis_adapter import build_project
        from unittest.mock import patch
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'keep.p2dx';p.write_text('original')
            with patch('pitbuilder.plaxis_adapter.launch_owned',side_effect=AssertionError('unexpected launch')):
                with self.assertRaises(ValueError):build_project({},p,Path('unused.exe'),Path(d),payload={})
            self.assertEqual(p.read_text(),'original')
    # 模拟已有 Input 进程，断言启动函数在创建新进程前就明确拒绝。
    def test_existing_input_rejected_before_launch(self):
        from unittest.mock import patch
        from pitbuilder.plaxis_adapter import launch_owned
        with patch('pitbuilder.legacy.importer.plaxis_running',return_value=True),patch('subprocess.Popen',side_effect=AssertionError('unexpected launch')):
            with self.assertRaises(ValueError):launch_owned('not-used.exe')

    # 分别检查坑内已挖、坑内保留和坑外土体；跨墙或跨开挖面的土簇必须报错。
    def test_split_bbox_rejects_crossing(self):
        from pitbuilder.plaxis_adapter import soil_state
        self.assertFalse(soil_state([10,-2,30,0],10,30,-2))
        self.assertTrue(soil_state([10,-5,30,-2],10,30,-2))
        self.assertTrue(soil_state([0,-2,10,0],10,30,-2))
        with self.assertRaises(ValueError):soil_state([9,-2,30,0],10,30,-2)
        with self.assertRaises(ValueError):soil_state([10,-3,30,-1],10,30,-2)
    # 总阻力 50 只分给外侧、内侧为 0，防止两侧重复施加有限阻力。
    def test_leak_outside_material_on_both_sides_not_allowed(self):
        from pitbuilder.plaxis_adapter import interface_resistances
        self.assertEqual(interface_resistances(50),{'outside':50,'inside':0})
    # 同时翻转左右墙及首末点方向，断言墙外侧的正负界面随真实线方向变化。
    def test_positive_side_depends_on_actual_direction(self):
        from pitbuilder.plaxis_adapter import outside_positive
        self.assertFalse(outside_positive('left',0,-12))
        self.assertTrue(outside_positive('right',0,-12))
        self.assertTrue(outside_positive('left',-12,0))
        self.assertFalse(outside_positive('right',-12,0))
    # 核对枚举数字后缀、属性名大小写和数值单位不会造成错误的材料比较差异。
    def test_material_enum_echo_normalization(self):
        from pitbuilder.plaxis_adapter import material_value
        self.assertEqual(material_value('    CrossPermeability: Semi-permeable (1)\n','CrossPermeability','Semi-permeable'),'Semi-permeable')
        self.assertEqual(material_value('    EA1: 10000000 kN/m\n','EA1',10000000),10000000)
        self.assertEqual(material_value('    cRef: 10 kN/m2\n','cref',10),10)

if __name__=='__main__':unittest.main()
