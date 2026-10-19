import unittest
from unittest.mock import patch,Mock
import bootstrap
class BootstrapTests(unittest.TestCase):
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
if __name__=='__main__':unittest.main()
