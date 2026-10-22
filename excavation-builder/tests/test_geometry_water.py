# 【模块中文说明】
# 离线单元测试：验证切分归属、水力设施约束、分支漏水和嵌套差异定位。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
from pathlib import Path
import unittest
from test_rules import sample

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Geometry(unittest.TestCase):
    # 观测土区完整位于逻辑层和坑内时可归类；只要跨坑边界，即使中心点在坑内也应拒绝。
    def test_region_contains_not_centroid(self):
        from pitbuilder.geometry import plan_geometry,classify_cut_objects
        from pitbuilder.stages import compile_stages
        c=sample();plan=plan_geometry(c,compile_stages(c))
        obs=[{'name':'NEW-SOIL','layer_id':'L1','polygon':[[10,-2],[30,-2],[30,-5],[10,-5]]}]
        result=classify_cut_objects(plan,obs)
        self.assertEqual(result['NEW-SOIL']['material_id'],'SOIL')
        self.assertTrue(result['NEW-SOIL']['inside_pit'])
        obs[0]['polygon']=[[9,-2],[30,-2],[30,-5],[9,-5]]
        with self.assertRaises(ValueError):classify_cut_objects(plan,obs)

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Water(unittest.TestCase):
    # 测试辅助入口：调用生产阶段或水力编译器，返回真实完整状态供断言；不建立软件会话。
    def compile(self,c):
        from pitbuilder.geometry import plan_geometry
        from pitbuilder.stages import compile_stages
        from pitbuilder.hydraulics import compile_hydraulics
        stages=compile_stages(c)
        return compile_hydraulics(c,stages,plan_geometry(c,stages))
    # 检查水力计划的外/内侧阻力分配、等效线类型及保留土体不被设为 Dry。
    def test_leak_resistance_not_doubled(self):
        h=self.compile(sample())['D1']
        self.assertEqual(h['leaks'][0]['outside_resistance_days'],50)
        self.assertEqual(h['leaks'][0]['inside_resistance_days'],0)
        self.assertEqual(h['boundary']['mode'],'equivalent_head')
        self.assertFalse(h['dry_active_soils'])
    # 去掉设施坐标，断言只有目标水头而没有位置时不能生成排水方案。
    def test_missing_drain_location(self):
        c=sample();c['hydraulic_plans'][0].pop('points')
        with self.assertRaises(ValueError):self.compile(c)
    # 逐项核对 true/false 文字与真实布尔值的等价性，未知文字必须报错，不能靠字符串真假判断。
    def test_explicit_seepage_boolean_strings(self):
        for flag,want in [('false',False),('FALSE',False),('true',True),(False,False),(True,True)]:
            c=sample();c['hydraulic_plans'][0]['seepage']=flag
            self.assertIs(self.compile(c)['D1']['boundary']['seepage'],want)
        c=sample();c['hydraulic_plans'][0]['seepage']='maybe'
        with self.assertRaises(ValueError):self.compile(c)
    # 把正常排水线规定水头放到线标高之下，断言当前工具拒绝这种吸力控制输入。
    def test_normal_drain_cannot_impose_suction(self):
        c=sample();c['hydraulic_plans'][0].update(mode='drain',head=-4)
        with self.assertRaises(ValueError):self.compile(c)
    # 把方案类型改为入渗，断言工具不会把正入流条件当成坑内自然排水。
    def test_boundary_infiltration_not_accepted_as_seepage(self):
        c=sample();c['hydraulic_plans'][0]['mode']='infiltration'
        with self.assertRaises(ValueError):self.compile(c)
    # 增加与漏水阶段无祖先关系的分支，断言该分支不会因表格顺序相邻而继承漏水。
    def test_leak_not_inherited_into_unrelated_branch(self):
        c=sample();c['stages'].insert(2,{'id':'OTHER','previous':'W1','operation':'wait','duration_days':0.1})
        self.assertEqual(self.compile(c)['OTHER']['leaks'],[])

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Verification(unittest.TestCase):
    # 只改变一个嵌套激活属性，断言差异记录准确包含阶段、对象和属性路径。
    def test_nested_mismatch_names_affected_object(self):
        from pitbuilder.verify import compare_state
        mismatches=compare_state({'E1':{'soil':{'active':False,'head':-3}}},{'E1':{'soil':{'active':True,'head':-3}}})
        self.assertEqual(mismatches[0]['path'],'E1.soil.active')
    # 即使 p2dx 主文件不存在，只要同名 dat 目录已存在，也必须拒绝输出。
    def test_target_dat_alone_blocks_overwrite(self):
        from pitbuilder.verify import check_output
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.p2dx';Path(str(p)+'dat').mkdir()
            with self.assertRaises(ValueError):check_output(p)

if __name__=='__main__':unittest.main()
