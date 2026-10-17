import socket
import unittest
from unittest.mock import patch
import evidence
import research

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.plan={'core_terms':['数据治理'],'english_terms':['data governance']}
        self.brief={'topic':'数据治理','period':'5'}
        self.item={'type':'policy','title':'关于数据治理的指导意见','url':'https://www.example.gov.cn/policy/2025/test.html','date':'','excerpt':''}
        self.article={'title':'关于推进数据产业的指导意见','text':'第一条，加强公共数据治理，完善数据质量管理制度。\n'+'正文用于验证文章内容和筛选机制，不包含导航列表。\n'*16,'date':'2025-01-01','url':self.item['url'],'link_density':0,'truncated':False,'content_status':'已提取正文','fetched_at':'2026-10-14'}

    def test_user_negative_examples_rejected_before_network(self):
        for url,title in [('https://www.tsinghua.edu.cn/en/','Tsinghua University'),('https://hudong.moe.gov.cn/qggxmd/','全国普通高等学校名单')]:
            with patch.object(evidence,'read_article') as read:
                item,reason=evidence.verify(dict(self.item,url=url,title=title),self.plan,self.brief)
                self.assertIsNone(item);read.assert_not_called()

    def test_policy_body_match_keywords_and_preview(self):
        with patch.object(evidence,'read_article',return_value=self.article):
            item,_=evidence.verify(self.item,self.plan,self.brief)
        self.assertIn('数据治理',item['keywords']);self.assertTrue(60<=item['relevance']<=100)
        self.assertIn('公共数据治理',item['content'])
        with patch.dict(research.JOBS,{'evidence-test':{'items':[dict(item,id='R1')],'status':'done'}}):
            self.assertNotIn('content',research.status({'id':'evidence-test'})['items'][0])
            self.assertIn('公共数据治理',research.preview({'id':'evidence-test','item_id':'R1'})['content'])

    def test_unrelated_body_and_policy_type_rejected(self):
        article=dict(self.article,text='高校招生与校园活动信息。'*40)
        with patch.object(evidence,'read_article',return_value=article):
            self.assertIsNone(evidence.verify(self.item,self.plan,self.brief)[0])
        with patch.object(evidence,'read_article',return_value=dict(self.article,title='数据治理研讨会召开')):
            self.assertIsNone(evidence.verify(self.item,self.plan,self.brief)[0])

    def test_news_requires_date_and_full_content(self):
        with patch.object(evidence,'read_article',return_value=dict(self.article,title='数据治理研讨会召开')):
            self.assertIsNotNone(evidence.verify(dict(self.item,type='news'),self.plan,self.brief)[0])
        with patch.object(evidence,'read_article',return_value=dict(self.article,date='')):
            self.assertIsNone(evidence.verify(dict(self.item,type='news'),self.plan,self.brief)[0])

    def test_paper_requires_core_concept_not_just_university(self):
        item=dict(self.item,type='papers',title='University rankings overview',excerpt='An overview of education institutions.')
        self.assertIsNone(evidence.verify(item,self.plan,self.brief)[0])
        item.update(title='Data governance in universities',excerpt='Study of data governance mechanisms.')
        self.assertIsNotNone(evidence.verify(item,self.plan,self.brief)[0])

    def test_extraction_removes_scripts_and_navigation(self):
        raw=('<html><head><title>测试</title><meta name="PubDate" content="2025-02-03"></head><body><nav>网站首页 用户中心</nav><div class="TRS_Editor"><h1>数据治理办法</h1><p>'+('加强数据治理和质量管理。'*30)+'</p></div><script>alert(1)</script><footer>友情链接</footer></body></html>').encode()
        article=evidence.extract_html(raw)
        self.assertIn('数据治理',article['text']);self.assertNotIn('alert',article['text']);self.assertNotIn('友情链接',article['text']);self.assertEqual(article['date'],'2025-02-03')

    def test_local_targets_blocked(self):
        for url in ['http://127.0.0.1/','http://192.168.0.2/','file:///c:/test','http://198.18.0.2/']:
            with self.assertRaises(ValueError):evidence.public_url(url)
        with patch.object(evidence,'fake_dns_enabled',return_value=False),patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',80))]):
            with self.assertRaises(ValueError):evidence.public_url('https://public.example.com/path')

if __name__=='__main__':unittest.main()
