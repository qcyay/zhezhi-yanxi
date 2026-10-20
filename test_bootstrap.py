import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import bootstrap
class BootstrapTests(unittest.TestCase):
 def setUp(self):
  self.original_cwd=os.getcwd()
  self.temporary=tempfile.TemporaryDirectory()
  self.root_patch=patch.object(bootstrap,'ROOT',Path(self.temporary.name))
  self.root_patch.start()
 def tearDown(self):
  os.chdir(self.original_cwd)
  self.root_patch.stop()
  self.temporary.cleanup()
 def test_existing_dependencies_launch_without_install(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=[]),patch.object(bootstrap.sys,'argv',['bootstrap.py','--no-browser']),patch.object(bootstrap.runpy,'run_path') as run,patch.object(bootstrap.subprocess,'run') as pip:
   self.assertEqual(bootstrap.main(),0);pip.assert_not_called();run.assert_called_once();self.assertIn('--no-browser',bootstrap.sys.argv)
 def test_missing_dependencies_install_locally_and_restart(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=['xlrd']),patch.object(bootstrap.sys,'argv',['bootstrap.py','--check']),patch.object(bootstrap.subprocess,'run',return_value=Mock(returncode=0)) as pip,patch.object(bootstrap.subprocess,'call',return_value=0) as restart:
   self.assertEqual(bootstrap.main(),0);self.assertIn('--target',pip.call_args.args[0]);self.assertIn(str(bootstrap.ROOT/'.deps'),pip.call_args.args[0]);self.assertIn('--check',restart.call_args.args[0]);self.assertIn('--dependencies-ready',restart.call_args.args[0])
 def test_install_failure_does_not_launch(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=['xlrd']),patch.object(bootstrap.sys,'argv',['bootstrap.py']),patch.object(bootstrap.subprocess,'run',return_value=Mock(returncode=1)),patch.object(bootstrap.runpy,'run_path') as run:
   self.assertEqual(bootstrap.main(),1);run.assert_not_called()
 def test_restart_guard(self):
  with patch.object(bootstrap,'missing_dependencies',return_value=['xlrd']),patch.object(bootstrap.sys,'argv',['bootstrap.py','--dependencies-ready']),patch.object(bootstrap.subprocess,'run') as pip:
   self.assertEqual(bootstrap.main(),1);pip.assert_not_called()
 def test_dependency_probe_is_isolated(self):
  with patch.object(bootstrap.subprocess,'run',return_value=Mock(returncode=0,stdout='["xlrd"]')) as probe:
   self.assertEqual(bootstrap.missing_dependencies(),['xlrd']);self.assertIn('-c',probe.call_args.args[0]);self.assertTrue(probe.call_args.kwargs['capture_output'])
 def test_concurrent_installer_is_rejected(self):
  import msvcrt,tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as td,patch.object(bootstrap,'ROOT',Path(td)):
   with (Path(td)/'.setup.lock').open('a+b') as lock:
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
     with patch.object(bootstrap.subprocess,'run') as pip:
      self.assertEqual(bootstrap.install_dependencies(['unused']),1);pip.assert_not_called()
    finally:
     lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':unittest.main()
