import json,unittest
from unittest.mock import patch
import research,reader,policies,evidence
class ReaderTests(unittest.TestCase):
 def setUp(self):
  self.item={'id':'R1','local_id':'P1','type':'policy','title':'数据管理办法','content':'依据《中华人民共和国数据安全法》制定。数据治理正文。','url':'','keywords':['数据治理']}
  self.other={'id':'P2','local_id':'P2','type':'policy','title':'中华人民共和国数据安全法','content':'数据安全制度','url':''}
  self.job={'id':'j','items':[self.item],'related_items':{},'policy_directory':'private'}
  p=patch.dict(research.JOBS,{'j':self.job});p.start();self.addCleanup(p.stop)
 def test_policy_graph_evidence_and_counts(self):
  with patch.object(policies,'records',return_value=([self.item,self.other],[])):
   g=reader.policy_graph(self.item,'x');self.assertEqual(g['edges'],[{'source':'P1','target':'P2'}]);self.assertEqual(next(n for n in g['nodes'] if n['id']=='P2')['citation_count'],1)
 def test_public_status_omits_private_and_cached_body(self):
  self.item.update(local_path='secret',_summary={'text':'body'},content='long body');self.job['related_items']={'x':self.other}
  data=research.status({'id':'j'});self.assertNotIn('policy_directory',data);self.assertNotIn('related_items',data);self.assertNotIn('content',data['items'][0]);self.assertNotIn('_summary',data['items'][0]);self.assertNotIn('local_path',data['items'][0])
 def test_summary_basis_and_cache(self):
  calls=[]
  def model(msg):calls.append(msg);return {'answer':json.dumps({'summary':'文章介绍数据管理制度。'})}
  a=reader.summary({'id':'j','item_id':'R1'},model);b=reader.summary({'id':'j','item_id':'R1'},model);self.assertEqual(a,b);self.assertEqual(len(calls),1)
 def test_scan_never_summarizes_unread_text(self):
  self.item['scanned']=True
  with patch.object(research,'fetch',side_effect=AssertionError):self.assertIn('扫描',reader.summary({'id':'j','item_id':'R1'},None)['text'])
 def test_fulltext_keeps_abstract_when_unavailable(self):
  self.item.update(type='papers',doi='10.1/test',content='Only abstract')
  with patch.object(research,'fetch',side_effect=TimeoutError):
   data=reader.fulltext({'id':'j','item_id':'R1'});self.assertFalse(data['fulltext_available']);self.assertEqual(data['content'],'Only abstract');self.assertIn('仅保留数据库摘要',data['fulltext_notice'])
 def test_crossref_fallback_unknown_neighbor_count(self):
  self.item.update(type='papers',doi='10.1/test')
  with patch.object(reader,'academic',side_effect=TimeoutError),patch.object(research,'fetch',return_value=json.dumps({'message':{'is-referenced-by-count':9,'reference':[{'DOI':'10.2/ref'}]}}).encode()):
   graph=reader.paper_graph(self.item);self.assertEqual(graph['nodes'][0]['citation_count'],9);self.assertIsNone(graph['nodes'][1]['citation_count']);self.assertEqual(len(graph['edges']),1)
 def test_older_foundational_policy_toggle(self):
  self.item.update(date='2018-01-01',local_path='test.pdf',content_status='本地 PDF 全文',content='数据管理制度。'*50)
  brief=research.validate({'topic':'数据治理','types':['policy']})
  self.assertIsNotNone(evidence.verify(self.item,{'core_terms':['数据治理']},brief)[0]);brief['include_older_policies']=False
  self.assertIsNone(evidence.verify(self.item,{'core_terms':['数据治理']},brief)[0])
 def test_full_html_not_truncated(self):
  article=evidence.extract_html(('<html><title>政策</title><article>'+('数据管理正文。'*15000)+'最后一段</article></html>').encode('utf-8'))
  self.assertTrue(article['text'].endswith('最后一段'));self.assertGreater(len(article['text']),80000)
if __name__=='__main__':unittest.main()

