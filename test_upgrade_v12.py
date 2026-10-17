import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import app,decision,influence,knowledge
class Upgrade12Tests(unittest.TestCase):
 def test_citations_unknown_zero_and_authority(self):
  self.assertIsNone(influence.metric({'type':'papers'})['score'])
  self.assertEqual(influence.metric({'type':'papers','citation_count':0})['score'],1)
  self.assertGreater(influence.metric({'type':'papers','citation_count':100})['score'],influence.metric({'type':'papers','citation_count':10})['score'])
  self.assertEqual(influence.metric({'type':'policy','url':'https://www.moe.gov.cn/a'})['score'],85)
  self.assertIsNone(influence.metric({'type':'policy','url':'https://moe.gov.cn.fake.org/a'})['score'])
 def test_decision_validation(self):
  with self.assertRaises(ValueError):decision.validate({'title':'测试','context':'不足'})
  with self.assertRaises(ValueError):decision.validate({'title':'测试','context':'这里是足够长度的背景信息','outline':['一个章节']})
 def test_decision_grounding_persistence_and_full_source(self):
  brief=decision.validate({'title':'决策测试','context':'背景信息用于测试报告引用与完整材料展示'})
  def model(messages):return {'answer':json.dumps({'sections':[{'title':'现状','claims':[{'text':'有引用的背景事实','kind':'fact','citations':[{'id':'U1-P1','quote':'背景信息用于测试报告'}]},{'text':'应删除的虚构事实','kind':'fact','citations':[{'id':'U1-P1','quote':'这段引用不存在'}]},{'text':'建议开展后续调查。','kind':'proposal','citations':[]}]}],'questions':['需要哪些补充证据？']},ensure_ascii=False)}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);job={'id':'decision-test-id','brief':brief,'status':'running','created':1,'title':brief['title'],'issues':[]}
   decision.run(job,model,app.extract,root)
   self.assertEqual(job['status'],'done');self.assertEqual(len(job['sections'][0]['claims']),2)
   self.assertIn('仅基于',job['basis']);self.assertTrue(job['issues'])
   saved=decision.status({'id':job['id']},root);self.assertNotIn('chunks',saved)
   source=decision.source({'id':job['id'],'source_id':'U1-P1'},root);self.assertIn('完整材料展示',source['paragraphs'][0]['text'])
 def test_unreadable_files_never_silently_fallback(self):
  with tempfile.TemporaryDirectory() as td,patch.dict(knowledge.UPLOADS,{'file':{'path':str(Path(td)/'missing.txt'),'name':'missing.txt'}}):
   brief=decision.validate({'title':'失败测试','context':'这里是用于检查读取失败的背景信息','file_ids':['file']});job={'id':'failed-test-id','brief':brief,'status':'running','issues':[]}
   decision.run(job,lambda m:self.fail('must not call model'),app.extract,Path(td));self.assertEqual(job['status'],'error');self.assertIn('均未读取成功',job['message'])
 def test_graph_final_verification_preserves_edge_ids(self):
  for resolved in (None,{'id':'doi:verified','title':'关联测试文件','url':'https://doi.org/10.1234/verified','source':'Crossref','type':'papers'}):
   with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'source.txt';p.write_text('仅用于核验流程的原始测试材料。','utf-8')
    job={'id':'verify-test-id','depth':1,'fanout':2,'status':'running','progress':0}
    root={'id':'A','title':'导入材料','doi':'10.1234/a','source':'Crossref','url':'https://doi.org/10.1234/a'}
    target={'id':'B','title':'关联测试文件','source':'Crossref 参考文献','type':'reference'}
    with patch.object(knowledge,'metadata',return_value=root),patch.object(knowledge,'neighbors',return_value=([(target,'out','来源数据库参考文献')],[])),patch.object(knowledge,'resolve_reference',return_value=resolved):knowledge.run(job,[{'id':'file','name':p.name,'path':str(p)}],None,app.extract)
    self.assertEqual(job['status'],'done');node=next(n for n in job['nodes'] if n['id']=='B')
    self.assertEqual(job['edges'][0]['target'],'B')
    if resolved:self.assertEqual(node['verification'],'verified_metadata');self.assertEqual(node['url'],resolved['url'])
    else:self.assertEqual(node['verification'],'unverified');self.assertIn('bing.com/search',node['search_url'])
if __name__=='__main__':unittest.main()
