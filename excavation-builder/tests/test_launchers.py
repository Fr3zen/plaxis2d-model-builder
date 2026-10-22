import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name=='nt','Requires Windows cmd.exe')
class WindowsLaunchers(unittest.TestCase):
    def test_both_cmd_entries_reach_python_help(self):
        for name in ['检查与预览.cmd','基坑自动建模.cmd']:
            with self.subTest(entry=name):
                command='"'+os.environ['COMSPEC']+'" /d /s /c ""'+str(ROOT/name)+'" --help"'
                result=subprocess.run(command,input=b'\r\n',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,cwd=str(ROOT.parent))
                self.assertEqual(result.returncode,0,repr(result.stderr))
                self.assertIn(b'--validate-only',result.stdout)
                self.assertEqual(result.stderr,b'')

    def test_cmd_sources_use_windows_lines_and_ascii(self):
        for name in ['检查与预览.cmd','基坑自动建模.cmd','run_builder.cmd']:
            with self.subTest(entry=name):
                data=(ROOT/name).read_bytes()
                data.decode('ascii')
                self.assertNotIn(b'\n',data.replace(b'\r\n',b''))

if __name__=='__main__':unittest.main()
