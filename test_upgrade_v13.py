import unittest,json
from unittest.mock import patch
import fusion,citations,knowledge,research
class ReliabilityTests(unittest.TestCase):
 def test_truncation_retries_without_accepting_partial_data(self):
  calls=[]
  def model(messages):
   calls.append(messages)
   return {'answer':'{"facts":[]}' if len(calls)>1 else '{"facts":[','finish_reason':'stop' if len(calls)>1 else 'length'}
  self.assertEqual(fusion.prompt('提取facts',{},model),{'facts':[]});self.assertEqual(len(calls),2);self.assertIn('从头生成',calls[1][0]['content'])
 def test_retry_is_bounded(self):
  with patch.object(fusion,'decode',side_effect=ValueError('bad')) as decode:
   with self.assertRaisesRegex(ValueError,'三次'):fusion.prompt('task',{},lambda m:{'answer':'bad'})
   self.assertEqual(decode.call_count,3)
 def test_citation_fallback_verified_doi(self):
  with patch.dict(citations.CACHE,{},clear=True),patch.object(citations,'request',side_effect=[TimeoutError(),{'message':{'is-referenced-by-count':17}}]):
   self.assertEqual(citations.lookup('10.1234/test','test')['citation_count'],17)
 def test_title_mismatch_never_fills_count(self):
  with patch.dict(citations.CACHE,{},clear=True),patch.object(citations,'request',return_value={'results':[{'display_name':'unrelated','cited_by_count':300}]}):self.assertIsNone(citations.lookup('','data governance'))
 def test_sixty_files_allowed_and_sixtyone_rejected(self):
  records={str(i):{'name':str(i),'path':'fixture'} for i in range(61)}
  with patch.dict(knowledge.UPLOADS,records,clear=True),patch.dict(knowledge.JOBS,{},clear=True),patch.object(knowledge.POOL,'submit'):
   self.assertIn('id',knowledge.start({'file_ids':list(records)[:60]},None,None))
   with self.assertRaises(ValueError):knowledge.start({'file_ids':list(records)},None,None)
 def test_official_portal_never_returns_homepage(self):
  raw='<a href="https://www.gov.cn/">中国政府网数据治理首页</a><a href="https://www.gov.cn/zhengce/2026/content_123.html">关于加强数据治理的通知</a>'
  with patch.object(research,'fetch',return_value=raw.encode()):
   rows=research.official_portal('数据治理',{});self.assertTrue(rows);self.assertTrue(all('/zhengce/' in r['url'] for r in rows))
if __name__=='__main__':unittest.main()
