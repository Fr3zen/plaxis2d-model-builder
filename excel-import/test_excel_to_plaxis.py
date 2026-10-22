# 【模块中文说明】
# 原钻孔导入器的回归测试。
# 直接读取模板及构造的单元格数据，检查标高、面积、层序、尖灭和源表映射。
# 这些测试不启动 PLAXIS，修改导入逻辑时应与基坑工具测试一并运行。
# 
"""Input contract tests: no PLAXIS process or workbook writes."""
import copy
from pathlib import Path
import unittest

from excel_to_plaxis import load_excel, read_xlsx, parse_cells


# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class ExcelInputTests(unittest.TestCase):
    # 测试组初始化时读取一次钻孔模板及单元格快照，后续用例复制数据后再修改，避免彼此污染。
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).with_name('钻孔数据模板.xlsx')
        cls.cells = read_xlsx(cls.path)

    # 检查模板各钻孔界面和分层面积，保证读表结果与预期剖面一致。
    def test_template_elevations_and_area(self):
        from generate_strata import build_model
        data = load_excel(self.path)
        holes, _, _, report = build_model(data)
        self.assertEqual([h['x'] for h in holes], [0, 30, 70])
        self.assertEqual(holes[1]['bottoms'], [9, -2, -15])
        self.assertEqual(report['domain_area_m2'], 1800)
        self.assertEqual(list(report['region_areas_m2'].values()), [195, 610, 995])

    # 从正常模板复制一份单元格数据，施加一个无效输入，断言生产解析器明确拒绝。
    def rejected(self, coordinate, value, message):
        cells = copy.deepcopy(self.cells)
        cells[coordinate] = (value, cells[coordinate][1])
        with self.assertRaisesRegex(ValueError, message):
            parse_cells(cells)

    # 在标高位置放入公式标记，应指出单元格错误，不能读取公式缓存。
    def test_formula_rejected(self):
        self.rejected((2, 4), {'formula': True}, 'D2.*公式')

    # 删除必要层底标高，断言不把空值当作缺层或任意零标高。
    def test_missing_bottom_rejected(self):
        self.rejected((3, 5), None, 'E3')

    # 把层底改成普通文字，断言距离/标高字段必须为有限数值。
    def test_text_bottom_rejected(self):
        self.rejected((3, 5), '缺失', 'E3')

    # 令两孔处于相同横坐标，断言无法定义有效孔间区间时拒绝。
    def test_duplicate_x_rejected(self):
        self.rejected((3, 2), 0, 'distinct')

    # 构造层底高于层顶的倒置层，断言拒绝，零厚度相等情形仍允许。
    def test_inverted_layer_rejected(self):
        self.rejected((3, 4), 13, 'descend')

    # 重复钻孔编号应报错，避免不同位置的数据被当作同一个孔。
    def test_duplicate_id_rejected(self):
        self.rejected((3, 1), 'ZK1', 'unique')

    # 修改必要表头，断言解析器明确提示模板格式错误。
    def test_wrong_header_rejected(self):
        self.rejected((1, 3), '层底埋深(m)', 'A1:C1')

    # 打乱钻孔行顺序后，断言解析结果按横坐标排序，而非把表格顺序当作空间位置。
    def test_unsorted_rows_sorted_by_x(self):
        cells = copy.deepcopy(self.cells)
        for c in range(1, 7):
            cells[2, c], cells[4, c] = cells[4, c], cells[2, c]
        from generate_strata import build_model
        holes = build_model(parse_cells(cells))[0]
        self.assertEqual([h['id'] for h in holes], ['ZK1', 'ZK2', 'ZK3'])

    # 增加连续层底列，断言解析器按表头识别更多统一层位，不写死三层模板。
    def test_extra_layer_column_supported(self):
        cells = copy.deepcopy(self.cells)
        cells[1, 7] = ('基岩层底标高（m）', 'G1')
        for row in range(2, 5):
            cells[row, 7] = (-25, f'G{row}')
        # Move template notes to I; otherwise H title is not a layer header.
        for key in list(cells):
            if key[1] == 8:
                cells[key[0], 9] = cells.pop(key)
        data = parse_cells(cells)
        self.assertEqual(len(data['layers']), 4)

    # 构造中间孔层厚为零但两侧出现的层，断言几何可分段连接且层位身份不丢失。
    def test_layer_pinches_out_and_reappears(self):
        from generate_strata import build_model
        data = {'units': 'm', 'layers': [{'id':'upper'}, {'id':'lower'}],
                'boreholes': [
                    {'id':'A','x':0,'ground':0,'bottoms':[-2,-10]},
                    {'id':'B','x':10,'ground':0,'bottoms':[0,-10]},
                    {'id':'C','x':20,'ground':0,'bottoms':[-2,-10]}]}
        _, _, regions, report = build_model(data)
        self.assertEqual(regions[0]['polygon'].geom_type, 'MultiPolygon')
        self.assertEqual(regions[0]['polygon'].area, 20)
        self.assertEqual(report['domain_area_m2'], 200)
        self.assertEqual(report['gap_area_m2'], 0)
        self.assertEqual(report['overlap_area_m2'], 0)

    # 整条剖面某逻辑层均为零厚度时仍保留层序，同时不输出虚构的非零面积面。
    def test_whole_profile_zero_layer_is_retained(self):
        from generate_strata import build_model
        data = load_excel(self.path)
        data['layers'].insert(0, {'id':'absent','name':'缺失层','color':'#FFFFFF'})
        for hole in data['boreholes']:
            hole['bottoms'].insert(0,hole['ground'])
        _, _, regions, report = build_model(data)
        self.assertEqual(len(regions),4)
        self.assertTrue(regions[0]['polygon'].is_empty)
        self.assertEqual(report['all_zero_layer_ids'], ['absent'])
        self.assertEqual(report['domain_area_m2'],1800)

    # 核对 27 层案例转换后所有孔的源界面标高和零厚度记录均保留。
    def test_section1_all_source_interfaces_preserved(self):
        from generate_strata import build_model
        path = self.path.parent / 'converted_section1' / 'Section1_钻孔导入格式_27层.xlsx'
        if not path.exists():
            self.skipTest('Section1 user workbook not available')
        data = load_excel(path)
        _, _, _, report = build_model(data)
        self.assertEqual(len(data['boreholes']),13)
        self.assertEqual(len(data['layers']),27)
        self.assertEqual(report['zero_thickness_at_boreholes'],177)
        self.assertEqual(report['all_zero_layer_ids'],['layer_2','layer_5','layer_27'])
        self.assertEqual(report['gap_area_m2'],0)
        self.assertLess(report['overlap_area_m2'],report['area_tolerance_m2'])


if __name__ == '__main__':
    unittest.main()
