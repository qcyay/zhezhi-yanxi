import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import research

class ResearchTests(unittest.TestCase):
    def setUp(self):
        portal=patch.object(research,'official_portal',return_value=[]);portal.start();self.addCleanup(portal.stop)
        enrichment=patch.object(research.citations,'enrich',side_effect=lambda x:x);enrichment.start();self.addCleanup(enrichment.stop)
        oa=patch.object(research,'openalex_search',return_value=[]);oa.start();self.addCleanup(oa.stop)
        local=patch.object(research.policies,'candidates',return_value=([],[]));local.start();self.addCleanup(local.stop)
        refs=patch.object(research,'reference_sources',return_value=[]);refs.start();self.addCleanup(refs.stop)
        self.brief=research.validate({'topic':'数据治理','types':['papers','policy'],'purpose':'调研','scope':'国内高校','period':'5'})
        self.item={'type':'papers','title':'Real paper','url':'https://doi.org/10.1/test','doi':'10.1/test','date':'2025','authors':'Author','publisher':'Journal','excerpt':'Data governance','source':'Crossref','query':'data governance'}

    def model(self,messages):
        if 'paper_queries' in messages[0]['content']:
            return {'answer':json.dumps({'strategy':'测试方案','core_terms':['数据治理'],'english_terms':['data governance'],'paper_queries':['data governance'], 'policy_queries':['数据治理'],'news_queries':[]})}
        return {'answer':json.dumps({'recommendations':[{'id':'R1','reason':'值得阅读','relevance':88,'quote':'Data governance','keywords':['governance']},{'id':'fake','reason':'虚构'}]})}

    def job(self):
        return {'id':'test-job','brief':self.brief,'status':'running','items':[]}

    def test_real_records_only_and_partial_failure(self):
        job=self.job()
        with patch.object(research,'crossref',return_value=[dict(self.item),dict(self.item)]), patch.object(research,'policy_search',side_effect=TimeoutError):
            research.run(job,self.model)
        self.assertEqual(job['status'],'done')
        self.assertEqual(len(job['items']),1)
        self.assertEqual(job['items'][0]['reason'],'值得阅读')
        self.assertTrue(any('连接失败' in s for s in job['warnings']))

    def test_empty_results_never_invent(self):
        job=self.job()
        with patch.object(research,'crossref',return_value=[]), patch.object(research,'policy_search',return_value=[]):
            research.run(job,self.model)
        self.assertEqual(job['items'],[])
        self.assertIn('没有取得',job['summary'])

    def test_official_domain_boundary(self):
        self.assertTrue(research.official_domain('www.zju.edu.cn'))
        self.assertFalse(research.official_domain('gov.cn.evil.com'))
        self.assertFalse(research.safe_url('javascript:alert(1)'))

    def test_archive_and_deduplicate(self):
        job=self.job();job.update(status='done',items=[dict(self.item,id='R1')])
        job['brief']['topic']='../../CON:数据治理'
        with patch.dict(research.JOBS,{'test-job':job}),tempfile.TemporaryDirectory() as temp:
            result=research.archive({'id':'test-job','ids':['R1']},temp)
            research.archive({'id':'test-job','ids':['R1']},temp)
            self.assertEqual(len(list(Path(temp).rglob('*.md'))),1)
            p=Path(temp)/result['paths'][0]
            self.assertTrue(p.resolve().is_relative_to(Path(temp).resolve()))
            self.assertIn('不是原文全文',p.read_text('utf-8'))

    def test_crossref_date_and_parser(self):
        raw={'message':{'items':[{'title':['Test'],'DOI':'10.1/test','published':{'date-parts':[[2025,2]]},'author':[{'given':'A','family':'B'}],'abstract':'<jats:p>Abstract</jats:p>'}]}}
        with patch.object(research,'fetch',return_value=json.dumps(raw).encode()) as fetch:
            items=research.crossref('data governance',self.brief)
            self.assertIn('from-pub-date',fetch.call_args.args[0])
            self.assertEqual(items[0]['date'],'2025-2')
            self.assertEqual(items[0]['excerpt'],'Abstract')

    def test_model_failure_and_invalid_brief(self):
        job=self.job()
        research.run(job,lambda _: {'answer':'not json'})
        self.assertEqual(job['status'],'error')
        with self.assertRaises(ValueError):
            research.validate({'topic':'数据治理','types':[]})

    def test_semantic_rejection_removes_candidate(self):
        def model(messages):
            if 'paper_queries' in messages[0]['content']:return self.model(messages)
            return {'answer':json.dumps({'recommendations':[{'id':'R1','relevance':20,'quote':'Data governance','reason':'只是提及，不切合需求'}]})}
        job=self.job()
        with patch.object(research,'crossref',return_value=[dict(self.item)]),patch.object(research,'policy_search',return_value=[]):
            research.run(job,model)
        self.assertEqual(job['items'],[])
        self.assertEqual(job['excluded'][0]['reason'],'语义复核不相关')

    def test_unverifiable_model_score_uses_rule_score(self):
        def model(messages):
            if 'paper_queries' in messages[0]['content']:return self.model(messages)
            return {'answer':json.dumps({'recommendations':[{'id':'R1','relevance':100,'quote':'Invented evidence','keywords':['Fake keyword']} ]})}
        job=self.job()
        with patch.object(research,'crossref',return_value=[dict(self.item)]),patch.object(research,'policy_search',return_value=[]):
            research.run(job,model)
        self.assertLess(job['items'][0]['relevance'],100)
        self.assertNotIn('Fake keyword',job['items'][0]['keywords'])

if __name__=='__main__':
    unittest.main()
