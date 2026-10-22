# 【模块中文说明】
# 离线单元测试：验证矩形包围盒完整包含与跨分区歧义的不同处理。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
import unittest
# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class RegionMapping(unittest.TestCase):
    # 包围盒完全包含时返回区域 ID，部分交叠无法明确归属时必须拒绝。
    def test_box_inside_and_ambiguous_intersection(self):
        from pitbuilder.region_math import containing_region
        r=[{'id':'A','polygon':[[0,-5],[10,-5],[10,0],[0,0]]}]
        self.assertEqual(containing_region([0,-5,10,0],r),'A')
        self.assertIsNone(containing_region([10,-5,20,0],r))
        with self.assertRaises(ValueError):containing_region([9,-5,11,0],r)

if __name__=='__main__':unittest.main()
