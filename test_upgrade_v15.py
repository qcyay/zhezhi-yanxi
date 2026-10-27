import unittest,tempfile,time,concurrent.futures,json
from pathlib import Path
from unittest.mock import patch
import knowledge as k,recommendations as rec,interests,research
class Upgrade15Tests(unittest.TestCase):
 def test_concurrent_memo_and_independent_results(self):
  calls=[]
  @k.memoized
  def slow_v15(x):
   calls.append(x);time.sleep(.08);return {'items':[x]}
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
   rows=list(pool.map(slow_v15,['v15']*6))
  self.assertEqual(len(calls),1);rows[0]['items'].append('changed');self.assertEqual(rows[1]['items'],['v15'])
 def test_failed_lookup_short_cache(self):
  calls=[]
  @k.memoized
  def missing_v15(x):calls.append(x);return None
  missing_v15('x');missing_v15('x');self.assertEqual(len(calls),1)
 def test_interest_log(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'interest.json';interests.record(p,'教育数字化','检索');interests.record(p,'教育数字化','问答');interests.record(p,'api_key private','问答');self.assertEqual(len(interests.read(p)),1);self.assertEqual(interests.read(p)[0]['source'],'问答')
 def test_first_open_has_editorial_cards_without_network(self):
  with tempfile.TemporaryDirectory() as td,patch.object(research,'run',side_effect=AssertionError('network forbidden')):
   result=rec.home(td,Path(td));self.assertGreater(len(result['items']),0);self.assertIn('尚未个性化',result['feed_label']);self.assertTrue(all(r['url'].startswith('https://www.nda.gov.cn/') for r in result['items']))
 def test_no_history_no_files_default_topic(self):
  with tempfile.TemporaryDirectory() as td,patch.object(rec,'HISTORY_PROVIDER',return_value=[]):
   def search(job,model):
    self.assertTrue(job['brief']['topic']);job.update(status='done',items=[],warnings=[])
   with patch.object(research,'run',side_effect=search):
    job={};rec.run(job,{},td,None,None,{'.txt'},Path(td)/'cache','key','');self.assertEqual(job['status'],'done')
if __name__=='__main__':unittest.main()
