import unittest,tempfile,base64,json
from pathlib import Path
from unittest.mock import patch
import knowledge,app,research
class GraphTests(unittest.TestCase):
 def test_upload_limits_and_original_download(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);data=b'Local original content'
   u=knowledge.upload({'name':'../../source.txt','data':base64.b64encode(data).decode()},root,app.SUPPORTED)
   self.assertEqual(u['name'],'source.txt');self.assertTrue(Path(knowledge.UPLOADS[u['id']]['path']).resolve().is_relative_to(root.resolve()))
   identity='graph-test-download';knowledge.JOBS[identity]={'_nodes':{'A':{'_path':knowledge.UPLOADS[u['id']]['path'],'_name':'source.txt'}}}
   try:self.assertEqual(knowledge.download({'id':identity,'node_id':'A'}),(data,'source.txt'))
   finally:knowledge.JOBS.pop(identity);knowledge.UPLOADS.pop(u['id'])
   with self.assertRaises(ValueError):knowledge.upload({'name':'x.exe','data':'eA=='},root,app.SUPPORTED)
   with self.assertRaises(ValueError):knowledge.upload({'name':'x.txt','data':'invalid'},root,app.SUPPORTED)
 def test_depth_direction_degree_and_no_private_paths(self):
  def nearby(n,limit):
   nxt={'A':'B','B':'C','C':'D'}.get(n['id']);return ([({'id':nxt,'title':nxt,'doi':'10.1234/'+nxt,'source':'fixture','type':'papers'},'out','数据库引用依据')] if nxt else []),[]
  for depth in (1,2):
   with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'fixture.txt';p.write_text('本地导入文件，测试引用网络。','utf-8');job={'id':'test-depth-'+str(depth),'status':'running','depth':depth,'fanout':4,'progress':0,'created':0}
    with patch.object(knowledge,'metadata',return_value={'id':'A','title':'根节点','doi':'10.1234/a','source':'fixture'}),patch.object(knowledge,'neighbors',side_effect=nearby),patch.object(knowledge,'resolve_reference',return_value=None):knowledge.run(job,[{'id':'upload','name':'fixture.txt','path':str(p)}],None,app.extract)
    self.assertEqual(job['status'],'done');self.assertEqual(len(job['edges']),depth);self.assertEqual(max(n['level'] for n in job['nodes']),depth);self.assertEqual(job['edges'][0]['source'],'A');self.assertEqual(job['edges'][0]['target'],'B')
    if depth==2:self.assertEqual(next(n['degree'] for n in job['nodes'] if n['id']=='B'),2)
    with patch.dict(knowledge.JOBS,{job['id']:job}):self.assertNotIn(str(p),json.dumps(knowledge.status({'id':job['id']})))
 def test_multiple_imports_form_verified_local_edge(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/'数据治理工作报告.txt';b=root/'公共数据管理办法.txt';a.write_text('本报告依据《公共数据管理办法》开展数据治理工作。','utf-8');b.write_text('公共数据管理办法：建立数据共享和安全管理制度。','utf-8')
   files=[{'id':str(i),'path':str(p),'name':p.name} for i,p in enumerate((a,b))];job={'id':'multi-test','depth':1,'fanout':4,'status':'running','created':0}
   with patch.object(knowledge,'metadata',return_value=None),patch.object(knowledge.research,'web_candidates',return_value=[]),patch.object(knowledge,'resolve_reference',side_effect=AssertionError('local match should not query network')):knowledge.run(job,files,None,app.extract)
   self.assertEqual(job['status'],'done');self.assertEqual(len(job['nodes']),2);self.assertEqual(job['edges'][0]['source'],'local:0');self.assertEqual(job['edges'][0]['target'],'local:1')
 def test_model_cannot_invent_reference(self):
  text='正文明确依据《数据管理办法》开展工作。'
  def model(_):return {'answer':json.dumps({'references':[{'title':'虚构文件','quote':'不存在的原文引用','doi':'10.1234/fake'}]})}
  _,refs=knowledge.extract_refs(text,'工作报告',model);self.assertEqual([r['title'] for r in refs],['数据管理办法'])
 def test_threshold_validation(self):
  with patch.dict(knowledge.UPLOADS,{'known':{}}):
   for depth in (0,5,'bad'):
    with self.assertRaises(ValueError):knowledge.start({'file_ids':['known'],'depth':depth},None,None)
 def test_http_upload_job_status_and_download(self):
  import threading,time,urllib.request,urllib.error
  with tempfile.TemporaryDirectory() as td,patch.object(app,'DATA',Path(td)),patch.dict(knowledge.UPLOADS,{}),patch.dict(knowledge.JOBS,{}),patch.object(app,'research_model',return_value={'answer':'{"references":[]}'}),patch.object(knowledge,'metadata',return_value=None),patch.object(research,'web_candidates',return_value=[]):
   server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_port)
   def post(route,data,authorized=True):
    headers={'Content-Type':'application/json'}
    if authorized:headers['X-App-Token']=app.TOKEN
    with urllib.request.urlopen(urllib.request.Request(url+'/api/knowledge/'+route,data=json.dumps(data).encode(),headers=headers),timeout=5) as response:return response.read()
   try:
    with self.assertRaises(urllib.error.HTTPError) as error:post('upload',{},False)
    self.assertEqual(error.exception.code,403)
    raw='软件接口测试材料，核对原文下载。'.encode();uploaded=json.loads(post('upload',{'name':'接口测试.txt','data':base64.b64encode(raw).decode()}));job=json.loads(post('start',{'file_ids':[uploaded['id']],'depth':1}))
    for _ in range(100):
     status=json.loads(post('status',job))
     if status['status']!='running':break
     time.sleep(.02)
    self.assertEqual(status['status'],'done');self.assertEqual(post('download',dict(job,node_id=status['nodes'][0]['id'])),raw)
   finally:server.shutdown();server.server_close();thread.join()
 def test_openalex_abstract_and_pagination(self):
  data={'results':[{'id':'https://openalex.org/W1','display_name':'Data governance','publication_date':'2025-01-01','abstract_inverted_index':{'data':[0],'governance':[1],'works':[2]},'doi':'https://doi.org/10.1234/abc'}]}
  with patch.object(research,'fetch',return_value=json.dumps(data).encode()) as get:
   rows=research.openalex_search('data governance',{'period':'all','_offset':60});self.assertIn('page=2',get.call_args.args[0]);self.assertEqual(rows[0]['excerpt'],'data governance works');self.assertEqual(rows[0]['doi'],'10.1234/abc')
if __name__=='__main__':unittest.main()
