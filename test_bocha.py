import io,json,unittest,urllib.error
from unittest.mock import patch
import search_sources as source
class BochaTests(unittest.TestCase):
 def response(self,data):return io.BytesIO(json.dumps(data).encode())
 def test_real_request_shape(self):
  with patch.object(source,'KEY_PROVIDER',return_value='fake'),patch('urllib.request.urlopen',return_value=self.response({'code':200,'data':{'webPages':{'value':[{'name':'Example','url':'https://example.org'}]}}})) as call:
   result=source.test_connection();self.assertTrue(result['connected']);self.assertEqual(result['count'],1)
   request=call.call_args.args[0];self.assertEqual(json.loads(request.data)['count'],1);self.assertEqual(request.get_header('Authorization'),'Bearer fake')
 def test_missing_key_no_request(self):
  with patch.object(source,'KEY_PROVIDER',return_value=''),patch('urllib.request.urlopen') as call:
   with self.assertRaises(ValueError):source.test_connection()
   call.assert_not_called()
 def test_failure_statuses(self):
  for status in (401,402,403,429):
   with patch.object(source,'KEY_PROVIDER',return_value='fake'),patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.org',status,'error',{},None)):
    with self.assertRaisesRegex(ValueError,str(status)):source.test_connection()
 def test_business_error_and_bad_json(self):
  for data in ({'code':401,'data':{}},[]):
   with patch.object(source,'KEY_PROVIDER',return_value='fake'),patch('urllib.request.urlopen',return_value=self.response(data)):
    with self.assertRaises(ValueError):source.test_connection()
