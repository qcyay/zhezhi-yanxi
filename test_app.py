import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_patch = patch.object(app, 'CONFIG', self.root/'config.json')
        self.config_patch.start()
        app.INDEX.update(files=[], chunks=[], issues=[], directory='')
        (self.root/'政策').mkdir()
        (self.root/'政策'/'数字化.txt').write_text('高校教育数字化建设需要数据治理和教师培训。', 'utf-8')
        (self.root/'图片.png').write_bytes(b'example')
        app.save_settings({'directory': str(self.root), 'model': 'deepseek-flash'})

    def tearDown(self):
        self.config_patch.stop()
        self.temp.cleanup()

    def test_key_encryption_preserve_delete(self):
        app.save_settings({'api_key': 'test-not-a-real-key'})
        self.assertNotIn('test-not-a-real-key', app.CONFIG.read_text('utf-8'))
        self.assertEqual(app.protect(app.settings()['key'], True), 'test-not-a-real-key')
        self.assertNotIn('key', app.public_settings())
        app.save_settings({'api_key': ''})
        self.assertTrue(app.public_settings()['has_key'])
        app.save_settings({'clear_key': True})
        self.assertFalse(app.public_settings()['has_key'])

    def test_scan_retrieve_and_unsupported(self):
        result = app.scan()
        self.assertEqual(result['files'][0]['path'], '政策/数字化.txt')
        self.assertTrue(any('图片.png' in s for s in result['issues']))
        self.assertIn('数据治理', app.retrieve('数字化建设')[0]['text'])
        self.assertEqual(app.retrieve('astronomy'), [])

    def test_docx(self):
        p = self.root/'资料.docx'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>测试正文</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(app.extract(p), '测试正文')

    def test_chat_citations_history_and_opt_out(self):
        app.scan()
        with patch.object(app, 'deepseek', return_value={'answer': '资料说明 [S1]', 'usage': {}}) as fake:
            result = app.chat({'question': '数字化', 'history': [{'role':'system','content':'BAD'}]})
            self.assertEqual(result['sources'][0]['id'], 'S1')
            self.assertIn('数据治理', fake.call_args.args[0][0]['content'])
            self.assertNotIn('BAD', str(fake.call_args))
            self.assertEqual(app.chat({'question': '数字化','use_library':False})['sources'], [])
            self.assertNotIn('数据治理', fake.call_args.args[0][0]['content'])

    def test_api_payload_and_missing_key(self):
        with self.assertRaises(ValueError):
            app.deepseek([])
        app.save_settings({'api_key': 'fake-key'})
        response = io.BytesIO(json.dumps({'choices':[{'message':{'content':'回答'}}]}).encode())
        with patch('urllib.request.urlopen', return_value=response) as fake:
            self.assertEqual(app.deepseek([{'role':'user','content':'你好'}])['answer'], '回答')
            request = fake.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.deepseek.com/chat/completions')
            self.assertEqual(json.loads(request.data)['model'], 'deepseek-flash')

    def test_research_requests_structured_output(self):
        app.save_settings({'api_key': 'fake-key'})
        response = io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"summary":"ok"}'}}]}).encode())
        with patch('urllib.request.urlopen', return_value=response) as fake:
            app.research_model([{'role':'system','content':'Output JSON'}])
            payload = json.loads(fake.call_args.args[0].data)
            self.assertEqual(payload['response_format'], {'type':'json_object'})
            self.assertEqual(payload['thinking'], {'type':'disabled'})

if __name__ == '__main__':
    unittest.main()
