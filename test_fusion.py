import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app,fusion,research,folder_picker
class FusionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.storage=self.root/'reports';self.docs=self.root/'docs';self.docs.mkdir();(self.docs/'会议.txt').write_text('2026年10月1日会议决定由张老师负责资料梳理。\n验收工作尚未完成，需要确认测试结果。','utf-8')
 def model(self,messages):
  payload=json.loads(messages[1]['content'])
  if 'facts' in payload:return {'answer':json.dumps({'sections':[{'title':'工作进展','claims':payload['facts']}],'questions':['验收还有什么待办？']})}
  source=payload['paragraphs'][0];claims=[{'text':'会议明确资料梳理负责人。','citations':[{'id':source['id'],'quote':source['text']}]}]
  return {'answer':json.dumps({'facts':claims,'claims':claims,'sections':[{'title':'工作进展','claims':claims}]})}
 def test_read_generate_save_reload_and_source(self):
  corpus=fusion.inspect({'directory':str(self.docs)},app.extract,app.SUPPORTED)
  with patch.object(fusion.POOL,'submit',side_effect=lambda fn,*args:fn(*args)):
   result=fusion.start({'corpus_id':corpus['id'],'file_ids':['F1'],'title':'测试'},self.model,self.storage)
  data=fusion.status(result,self.storage);self.assertEqual(data['status'],'done');self.assertNotIn('chunks',data);self.assertTrue(data['sections'][0]['claims'][0]['citations'])
  fusion.JOBS.pop(result['id']);self.assertEqual(fusion.status(result,self.storage)['title'],'测试');self.assertIn('会议决定',fusion.source(dict(result,source_id='F1-P1'),self.storage)['text']);self.assertEqual(len(fusion.reports(self.storage)['reports']),1)
  answer=fusion.ask(dict(result,question='资料梳理由谁负责？'),self.model,self.storage);self.assertEqual(len(answer['claims']),1)
 def test_fabricated_citation_is_rejected(self):
  source={'id':'F1-P1','text':'这是文件中的真实原文段落。'}
  self.assertEqual(fusion.grounded([{'text':'虚构','citations':[{'id':'fake','quote':source['text']}]},{'text':'错引','citations':[{'id':'F1-P1','quote':'模型自己编造的原文'}]}],[source]),[])
 def test_optional_reference_and_duplicates(self):
  corpus=fusion.inspect({'directory':str(self.docs),'use_reference':True,'reference_directory':str(self.docs)},app.extract,app.SUPPORTED);self.assertEqual(len(corpus['files']),1)
 def test_no_source_path_traversal(self):
  with self.assertRaises(ValueError):fusion.get('../settings',self.storage)
 def test_xlsx_rows_and_formula_label(self):
  import openpyxl
  book=openpyxl.Workbook();sheet=book.active;sheet.title='任务清单';sheet.append(['负责人','状态']);sheet.append(['张老师','待验收']);sheet.append(['合计','=1+1']);path=self.docs/'任务.xlsx';book.save(path);book.close();text=app.extract(path);self.assertIn('任务清单】第2行',text);self.assertIn('公式（未计算结果）',text)
 def test_model_deadline_returns_retryable_error(self):
  import queue
  with patch.object(fusion.queue.Queue,'get',side_effect=queue.Empty):
   with self.assertRaisesRegex(ValueError,'3分钟'):fusion.prompt('test',{},lambda _: {'answer':'{}'})
 def test_folder_cancel(self):
  class Result:returncode=0;stdout='{"directory":"","cancelled":true}'
  with patch.object(folder_picker.subprocess,'run',return_value=Result()):self.assertTrue(folder_picker.choose()['cancelled'])
class RecallTests(unittest.TestCase):
 def test_supplement_reaches_twenty_without_duplicate_padding(self):
  brief=research.validate({'topic':'data governance','types':['papers']})
  def source(q,b):
   size=2 if not b.get('_offset') else 30
   return [dict(id='',type='papers',title='Data governance '+str(i),url='https://doi.org/10.1/'+str(i),doi='10.1/'+str(i),date='2026',authors='',publisher='',excerpt='Data governance improves institutional data quality.',source='fixture') for i in range(size)]
  def model(messages):
   if 'paper_queries' in messages[0]['content']:return {'answer':json.dumps({'strategy':'test','core_terms':['data governance'],'paper_queries':['data governance'],'policy_queries':[],'news_queries':[]})}
   return {'answer':'{"recommendations":[]}'}
  job={'id':'test','brief':brief,'items':[]}
  with patch.object(research.citations,'enrich',side_effect=lambda x:x),patch.object(research,'openalex_search',return_value=[]),patch.object(research,'crossref',side_effect=source),patch.object(research,'reference_sources',return_value=[]):research.run(job,model)
  self.assertEqual(job['status'],'done');self.assertGreaterEqual(len(job['items']),20);self.assertEqual(len({i['doi'] for i in job['items']}),len(job['items']))
if __name__=='__main__':unittest.main()
