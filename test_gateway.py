import io,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import app
class GatewayTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(app,'CONFIG',Path(self.temp.name)/'settings.json');self.patch.start();app.save_settings({'directory':self.temp.name,'api_key':'fake-key'})
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def test_gateway_and_structured_requests(self):
  app.save_settings({'api_endpoint':'https://modelgateway.zju.edu.cn/v1/','model':'deepseek-v4-flash-780k-local','api_key':'fake-campus'})
  with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode())) as call:
   app.research_model([{'role':'user','content':'test'}]);req=call.call_args.args[0];self.assertEqual(req.full_url,'https://modelgateway.zju.edu.cn/v1/chat/completions');self.assertNotIn('thinking',json.loads(req.data));self.assertEqual(req.get_header('Authorization'),'Bearer fake-campus')
 def test_change_endpoint_requires_new_key(self):
  with self.assertRaises(ValueError):app.save_settings({'api_endpoint':'https://modelgateway.zju.edu.cn/v1'})
  self.assertEqual(app.public_settings()['api_endpoint'],app.DEFAULT_ENDPOINT)
 def test_model_list_not_required(self):
  chat=io.BytesIO(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
  with patch('urllib.request.urlopen',side_effect=[chat,urllib.error.HTTPError('https://example.org',404,'missing',{},None)]) as call:
   r=app.test_connection();self.assertTrue(r['connected']);self.assertIn(app.settings()['model'],r['models']);self.assertIsNotNone(call.call_args_list[0].args[0].data)
 def test_failed_chat_cannot_be_green(self):
  with patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.org',401,'no',{},None)):
   with self.assertRaisesRegex(ValueError,'401'):app.test_connection()
 def test_endpoint_validation(self):
  for value in ['http://example.org/v1','https://user:secret@example.org/v1','https://example.org/v1?key=x','https://example.org/v1#x']:
   with self.assertRaises(ValueError):app.normalize_endpoint(value)
if __name__=='__main__':unittest.main()
