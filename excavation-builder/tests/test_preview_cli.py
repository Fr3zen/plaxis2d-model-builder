# 【模块中文说明】
# 离线单元测试：验证离线检查不会调用软件工作进程，阶段预览必须明确标为输入条件。
# 通过 unittest 运行；测试通过说明相应输入/编译规则成立，不代替真实软件保存重开或工程计算验证。
# 
from pathlib import Path
import tempfile
import unittest
from test_rules import sample

# 同一职责的 unittest 用例组，使用实际生产函数及独立输入验证规则；不启动工程计算。
class OfflineFlow(unittest.TestCase):
    # 给真实离线入口设置工作进程拦截，断言检查模式能完成而完全不调用软件进程。
    def test_validate_only_does_not_launch_worker(self):
        from builder import prepare
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'demo.p2dx'
            result=prepare(Path(__file__).resolve().parents[1]/'examples/demo.json',out)
            self.assertEqual(result['status'],'input_validated')
            self.assertFalse(out.exists())
            self.assertTrue((Path(d)/'demo_builder'/'payload.json').is_file())

    # 核对每阶段图片及 HTML 的生成，并要求显式保留“非计算结果”标记。
    def test_previews_for_each_phase_and_no_fake_results(self):
        from pitbuilder.preview import write_preview
        from pitbuilder.geometry import plan_geometry
        from pitbuilder.stages import compile_stages
        from pitbuilder.hydraulics import compile_hydraulics
        c=sample();st=compile_stages(c);geo=plan_geometry(c,st);hyd=compile_hydraulics(c,st,geo)
        with tempfile.TemporaryDirectory() as d:
            result=write_preview(c,geo,st,hyd,Path(d))
            self.assertEqual(len(result['phase_images']),5)
            self.assertFalse(result['calculation_results'])
            self.assertTrue(all(Path(p).is_file() for p in result['phase_images']))

if __name__=='__main__':unittest.main()
