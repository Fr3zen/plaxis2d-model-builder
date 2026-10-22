# 【模块中文说明】
# 离线单元测试：检查源码 ZIP 的目录关系、中文表头映射及敏感会话文件排除规则。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
from pathlib import Path
import tempfile,unittest,zipfile

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class Distribution(unittest.TestCase):
    # 打开真实生成的小 ZIP，检查旧模块依赖和中英文表头映射随包提供，探针/连接记录未混入。
    def test_archive_preserves_legacy_layout_and_omits_sessions(self):
        from build_distribution import package
        with tempfile.TemporaryDirectory() as d:
            p=package(Path(d)/'tool.zip',include_models=False)
            with zipfile.ZipFile(p) as z:
                names=z.namelist()
                self.assertIn('plaxis-strata/excavation-builder/builder.py',names)
                self.assertIn('plaxis-strata/excel-import/excel_to_plaxis.py',names)
                self.assertIn('plaxis-strata/excavation-builder/基坑建模模板.xlsx',names)
                self.assertIn('plaxis-strata/excavation-builder/pitbuilder/workbook_headers.json',names)
                self.assertFalse(any('/probes/' in n or 'capabilities.json' in n or 'node_modules' in n for n in names))

if __name__=='__main__':unittest.main()
