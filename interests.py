"""Small local interest log; no API credentials or full documents are stored."""
import json,time,threading,re
LOCK=threading.RLock()
def record(storage,topic,source):
 topic=str(topic or '').strip()[:100]
 if len(topic)<2 or re.search(r'sk-|api[_ -]?key|Bearer\s',topic,re.I):return
 with LOCK:
  rows=read(storage);rows=[r for r in rows if r['topic']!=topic];rows.insert(0,{'topic':topic,'source':source,'created':time.time()});storage.parent.mkdir(parents=True,exist_ok=True);temp=storage.with_suffix('.tmp');temp.write_text(json.dumps(rows[:50],ensure_ascii=False),'utf-8');temp.replace(storage)
def read(storage):
 try:
  data=json.loads(storage.read_text('utf-8'));return [r for r in data if isinstance(r,dict) and isinstance(r.get('topic'),str)][:50]
 except (OSError,ValueError,TypeError):return []
