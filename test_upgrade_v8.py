import unittest,tempfile,json,time,threading
from pathlib import Path
from unittest.mock import patch
import app,formats,fusion
class UpgradeTests(unittest.TestCase):
 def test_image_png_jpg_and_xls(self):
  from PIL import Image,ImageDraw,ImageFont
  import xlwt
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);im=Image.new('RGB',(1100,220),'white');ImageDraw.Draw(im).text((30,50),'项目会议决定：张老师负责资料整理。',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',40),fill='black')
   for suffix in ('.png','.jpg'):
    path=root/('会议'+suffix);im.save(path);text=app.extract(path);self.assertIn('张老师',text);self.assertIn('资料整理',text)
    with patch.object(formats,'image_text',side_effect=AssertionError('cache miss')):self.assertEqual(app.extract(path),text)
   book=xlwt.Workbook();sheet=book.add_sheet('责任清单');sheet.write(0,0,'张老师');sheet.write(0,1,'资料整理');path=root/'任务.xls';book.save(str(path));text=app.extract(path);self.assertIn('张老师',text);self.assertIn('责任清单',text)
 def test_valid_cache_and_invalid_not_reused(self):
  payload={'paragraphs':[{'id':'F1-P1','text':'这是原文中的准确引用资料。'}]};valid={'sections':[{'claims':[{'text':'事实','citations':[{'id':'F1-P1','quote':'这是原文中的准确引用'}]}]}]}
  with tempfile.TemporaryDirectory() as td:
   cache=Path(td)
   with patch.object(fusion,'prompt',return_value=valid) as call:
    self.assertFalse(fusion.cached_call('report',payload,None,cache,'m')[1]);self.assertTrue(fusion.cached_call('report',payload,None,cache,'m')[1]);self.assertEqual(call.call_count,1)
   with patch.object(fusion,'prompt',return_value={'sections':[]}) as call:
    fusion.cached_call('bad',payload,None,cache,'m');fusion.cached_call('bad',payload,None,cache,'m');self.assertEqual(call.call_count,2)
 def test_parallel_batches_and_progress(self):
  barrier=threading.Barrier(3);job={}
  def task():barrier.wait(timeout=2);return 'done',False
  result=fusion.parallel_stage(job,'提取要点',[(str(i),task) for i in range(3)],5,60)
  self.assertEqual(result,['done']*3);self.assertEqual(job['completed_batches'],3);self.assertEqual(job['progress'],60)
 def test_large_report_pipeline_reuses_completed_batches(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);docs=root/'docs';docs.mkdir();(docs/'大型工作记录.txt').write_text(('项目会议决定由张老师负责资料整理，验收仍然等待核查。'*60+'\n')*50,'utf-8')
   corpus=fusion.inspect({'directory':str(docs)},app.extract,app.SUPPORTED);calls=[]
   def model(messages):
    payload=json.loads(messages[1]['content']);calls.append(payload)
    if 'paragraphs' in payload:
     c=payload['paragraphs'][0];data={'facts':[{'text':'资料整理已经明确负责人。','citations':[{'id':c['id'],'quote':c['text'][:30]}]}]}
    else:data={'sections':[{'title':'工作进展','claims':payload['facts']}],'questions':['何时验收？']}
    return {'answer':json.dumps(data,ensure_ascii=False)}
   for i in range(2):
    job={**fusion.CORPORA[corpus['id']],'id':'large-'+str(i),'title':'测试','model_name':'test','created':0,'status':'running'};fusion.run(job,model,root/'reports');self.assertEqual(job['status'],'done');self.assertTrue(job['sections'])
    if i==0:first=len(calls);self.assertGreater(first,3)
    else:self.assertEqual(len(calls),first)
 def test_async_inventory_and_full_source(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'会议.txt').write_text('第一段会议决定，由张老师负责整理。\n第二段验收尚未完成，需要继续核查。','utf-8')
   task=fusion.start_inspect({'directory':td},app.extract,app.SUPPORTED)
   for _ in range(100):
    data=fusion.inspect_status(task)
    if data['status']!='running':break
    time.sleep(.02)
   self.assertEqual(data['status'],'done');self.assertEqual(data['completed_files'],1);self.assertEqual(data['tasks'][0]['status'],'done')
   corpus=fusion.CORPORA[data['result']['id']];fusion.JOBS['unit-full-source']={**corpus,'status':'done'}
   try:
    source=fusion.source({'id':'unit-full-source','source_id':'F1-P1'},root);self.assertEqual(len(source['paragraphs']),2);self.assertIn('第二段',source['paragraphs'][1]['text'])
   finally:fusion.JOBS.pop('unit-full-source',None)
if __name__=='__main__':unittest.main()
