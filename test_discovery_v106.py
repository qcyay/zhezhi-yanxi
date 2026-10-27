import unittest,tempfile,json,io
from pathlib import Path
from unittest.mock import patch
import recommendations as rec,research,evidence,knowledge,search_sources
class DiscoveryTests(unittest.TestCase):
 def test_news_case_and_policy_alias(self):
  brief={'topic':'高校数字化转型','period':'all'}
  for kind,title in [('news','高校数字化转型实践案例'),('policy','关于推进教育数字化的意见')]:
   item={'type':kind,'title':title,'url':'https://www.moe.gov.cn/srcsite/202504/t20250416_1187476.html','date':''}
   article={'title':title,'text':'教育数字化是高等教育的重要工作。'*30,'date':'','link_density':0,'url':item['url'],'truncated':False,'fetched_at':'today','content_status':'正文'}
   with patch.object(evidence,'read_article',return_value=article):
    result,reason=evidence.verify(item,{},brief)
   self.assertIsNotNone(result,reason);self.assertEqual(result['date'],'2025-04-16')
 def test_null_bocha_date(self):
  data={'code':200,'data':{'webPages':{'value':[{'name':'title','url':'https://example.org/a','datePublished':None}]}}}
  with patch.object(search_sources,'KEY_PROVIDER',return_value='fake'),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
   self.assertEqual(search_sources.search('topic')[0]['date'],'')
 def test_empty_openalex_references_uses_crossref(self):
  def request(url):
   if 'crossref' in url:return {'message':{'reference':[{'DOI':'10.1234/next','article-title':'Next paper'}]}}
   return {'results':[]}
  with patch.object(knowledge,'request',side_effect=request):
   rows,_=knowledge.neighbors({'doi':'10.1234/root','_openalex':{'id':'https://openalex.org/W1','referenced_works':[]}},4)
  self.assertTrue(any(n.get('doi')=='10.1234/next' and direction=='out' for n,direction,_ in rows))
 def test_short_recommendations_backfill_to_twelve(self):
  calls=[]
  def run(job,model):
   calls.append(job['brief']);batch=len(calls)
   job.update(status='done',warnings=[],items=[{'title':f'paper{batch}-{i}','url':f'https://example.org/{batch}/{i}','type':'papers','date':'2026-01-01','excerpt':'related evidence'} for i in range(5)])
  with tempfile.TemporaryDirectory() as td,patch.object(rec,'HISTORY_PROVIDER',return_value=[]),patch.object(research,'run',side_effect=run):
   job={};rec.run(job,{},td,None,None,{'.txt'},Path(td)/'cache','key','高校数字化转型')
   self.assertEqual(job['status'],'done');self.assertEqual(len(job['items']),12);self.assertEqual(len({rec.identity(i) for i in job['items']}),12)
   self.assertTrue(any(c['period']=='all' for c in calls))
