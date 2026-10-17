import unittest,tempfile,json,io,time
from pathlib import Path
from unittest.mock import patch
import recommendations as rec,search_sources,research
class RecommendationTests(unittest.TestCase):
 def test_batches_cache_and_library_change(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);docs=root/'docs';docs.mkdir();p=docs/'数据治理.txt';p.write_text('数据治理研究关注共享制度与数据质量。','utf-8');calls=[]
   def model(messages):return {'answer':json.dumps({'topics':[{'name':'数据治理','evidence':[{'id':'L1','quote':'数据治理研究关注'}]}]})}
   def search(job,model):
    calls.append(job['brief']);job.update(status='done',warnings=[],items=[{'id':'R'+str(i),'type':'papers','title':'文献'+str(i),'doi':'10.1234/'+str(i),'url':'https://doi.org/10.1234/'+str(i),'date':'2026-01-01','excerpt':'摘要内容','source':'fixture','reason':'主题匹配'} for i in range(15)])
   def run(next=False):
    job={'id':'test-job','status':'running'};rec.run(job,{'next':next},str(docs),model,lambda p:p.read_text('utf-8'),{'.txt'},root/'cache','key','');self.assertEqual(job['status'],'done');return job
   with patch.object(research,'run',side_effect=search):
    a=run();self.assertEqual(len(a['items']),12);self.assertEqual(a['items'][0]['related_files'],['数据治理.txt'])
    b=run(True);self.assertEqual(len(b['items']),3);self.assertFalse({rec.identity(i) for i in a['items']} & {rec.identity(i) for i in b['items']});self.assertEqual(len(calls),1)
    c=run();self.assertEqual(c['items'],b['items']);self.assertEqual(len(calls),1)
    p.write_text('数据治理研究关注共享制度与数据质量。补充材料。','utf-8');run();self.assertEqual(len(calls),2)
 def test_empty_library_uses_history(self):
  with tempfile.TemporaryDirectory() as td,patch.object(rec,'HISTORY_PROVIDER',return_value=[{'topic':'教育数字化','source':'检索记录'}]):
   def search(job,model):
    self.assertEqual(job['brief']['topic'],'教育数字化');job.update(status='done',items=[],warnings=[])
   with patch.object(research,'run',side_effect=search):
    job={};rec.run(job,{},td,None,None,{'.txt'},Path(td)/'cache','empty','');self.assertEqual(job['status'],'done');self.assertEqual(job['topics'][0]['name'],'教育数字化')
 def test_bocha_mapping_and_independent_key(self):
  response={'code':200,'data':{'webPages':{'value':[{'name':'公开政策','url':'https://www.gov.cn/a.html','snippet':'原始摘要','datePublished':'2026-10-01T00:00:00'}]}}}
  with patch.object(search_sources,'KEY_PROVIDER',return_value='test-bocha-only'),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as request:
   rows=search_sources.search('数据治理');self.assertEqual(rows[0]['source'],'博查搜索 API');self.assertEqual(rows[0]['date'],'2026-10-01');self.assertEqual(request.call_args.args[0].get_header('Authorization'),'Bearer test-bocha-only')
 def test_bocha_policy_boundary(self):
  with patch.object(search_sources,'search',return_value=[{'title':'伪官网','url':'https://gov.cn.example.org/a','excerpt':''},{'title':'真实来源','url':'https://www.gov.cn/a.html','excerpt':''}]):
   rows=research.bocha_records('治理',{'period':'1'},'policy');self.assertEqual(len(rows),1)
 def test_dates_sort_numerically(self):
  self.assertGreater(rec.date_key({'date':'2026-10-1'}),rec.date_key({'date':'2026-9-30'}));self.assertEqual(rec.date_key({'date':'unknown'}),0)
 def test_bocha_key_encrypted_and_not_in_public_settings(self):
  import app
  with tempfile.TemporaryDirectory() as td,patch.object(app,'CONFIG',Path(td)/'settings.json'):
   public=app.save_settings({'directory':td,'bocha_api_key':'fake-bocha-test-key'})
   self.assertTrue(public['has_bocha_key']);self.assertNotIn('fake-bocha-test-key',json.dumps(public));self.assertNotIn('fake-bocha-test-key',app.CONFIG.read_text('utf-8'))
   self.assertEqual(app.protect(app.settings()['bocha_key'],True),'fake-bocha-test-key')
   self.assertFalse(app.save_settings({'clear_bocha_key':True})['has_bocha_key'])
 def test_review_deadline_does_not_wait_for_worker(self):
  import threading
  release=threading.Event();started=time.monotonic()
  def slow(messages):release.wait(1);return {'answer':'{"recommendations":[]}'}
  try:
   with self.assertRaises(ValueError):research.review_batches(slow,[{'role':'system','content':'test'},{'role':'user','content':json.dumps({'records':[{'id':'R1'}]})}],timeout=.01)
   self.assertLess(time.monotonic()-started,.5)
  finally:release.set()
if __name__=='__main__':unittest.main()
