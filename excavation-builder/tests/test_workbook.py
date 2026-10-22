# 【模块中文说明】
# 离线单元测试：验证中英文表头等价、重复字段拒绝、中文模板及公式拒绝规则。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
from pathlib import Path
import unittest

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Workbook(unittest.TestCase):
    def test_stage_template_exposes_calculation_type_and_only_duration(self):
        from pitbuilder.legacy import read_xlsx
        from pitbuilder.workbook import parse_table
        p=Path(__file__).resolve().parents[1]/'基坑建模模板.xlsx'
        headers=[v[0] for (r,c),v in read_xlsx(p,'施工阶段').items() if r==1]
        self.assertIn('计算类型',headers)
        self.assertIn('孔压生成方式',headers)
        self.assertFalse(any('速度' in str(v) for v in headers))
        self.assertTrue(all('calculation_type' in s and 'duration_days' in s for s in parse_table(read_xlsx(p,'施工阶段'),'施工阶段')))
    # 给出同义的中文/英文施工表头，断言解析结果使用完全一致的内部键和值。
    def test_chinese_and_english_headers_are_equivalent(self):
        from pitbuilder.workbook import parse_table
        chinese={(1,1):('阶段编号','A1'),(1,2):('阶段历时（天）','B1'),(2,1):('E1','A2'),(2,2):(2.5,'B2')}
        english={(1,1):('id','A1'),(1,2):('duration_days','B1'),(2,1):('E1','A2'),(2,2):(2.5,'B2')}
        self.assertEqual(parse_table(chinese,'施工阶段'),parse_table(english,'施工阶段'))
    # 同时放入中文阶段编号和英文 id 两列，断言映射后重复字段被拒绝，不覆盖数据。
    def test_duplicate_alias_columns_rejected(self):
        from pitbuilder.workbook import parse_table
        with self.assertRaises(ValueError):parse_table({(1,1):('阶段编号','A1'),(1,2):('id','B1')},'施工阶段')
    # 逐表读取全部 11 张工作表，要求所有非空首行字段均包含中文标签。
    def test_template_all_first_rows_are_chinese(self):
        from pitbuilder.legacy import read_xlsx
        import re
        path=Path(__file__).resolve().parents[1]/'基坑建模模板.xlsx'
        for name in ['使用说明','工程','钻孔数据','地层材料','材料','围护结构','支撑与垫层','施工阶段','水力方案','漏水段','初始水条件']:
            headers=[v[0] for (r,c),v in read_xlsx(path,name).items() if r==1 and v[0]]
            self.assertTrue(headers,name)
            for header in headers:self.assertRegex(header,r'[\u4e00-\u9fff]',name)
    # 重读实际模板核对墙坐标、施工动作和水头，并构造公式标记验证其被拒绝。
    def test_read_workbook_roundtrip_and_reject_formulas(self):
        from pitbuilder.workbook import read_workbook, parse_table
        from unittest.mock import patch
        from workbook_fixture import workbook_cells
        with patch('pitbuilder.workbook.read_xlsx',side_effect=lambda path,name:workbook_cells()[name]):
            c=read_workbook(Path('fixture.xlsx'))
        self.assertEqual(c['walls'][1]['x'],30)
        self.assertEqual(c['stages'][2]['operation'],'excavate')
        self.assertEqual(c['hydraulic_plans'][0]['head'],-3)
        with self.assertRaises(ValueError):parse_table({(1,1):('ID','A1'),(2,1):({'formula':True},'A2')},'test')

if __name__=='__main__':unittest.main()
