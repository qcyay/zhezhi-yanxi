"""Cross-provider citation enrichment with bounded requests and reusable cache."""
import concurrent.futures,json,time,urllib.parse,urllib.request,threading
from difflib import SequenceMatcher
CACHE={};LOCK=threading.Lock()
def request(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ZheZhiYanXi/0.13 (research desktop)','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=5) as response:return json.loads(response.read(1500000))
def lookup(doi,title):
 key=(doi.lower(),title.lower())
 with LOCK:cached=CACHE.get(key)
 if cached and time.time()-cached[0]<3600:return cached[1]
 result=None;encoded=urllib.parse.quote(doi,safe='')
 endpoints=[]
 if doi:endpoints=[('OpenAlex','https://api.openalex.org/works/https://doi.org/'+encoded),('Crossref','https://api.crossref.org/works/'+encoded),('Semantic Scholar','https://api.semanticscholar.org/graph/v1/paper/DOI:'+encoded+'?fields=title,citationCount,url')]
 else:endpoints=[('OpenAlex','https://api.openalex.org/works?'+urllib.parse.urlencode({'search':title,'per-page':3}))]
 for source,url in endpoints:
  try:
   data=request(url)
   if source=='Crossref':data=data['message'];count=data.get('is-referenced-by-count')
   elif source=='Semantic Scholar':count=data.get('citationCount')
   else:
    if not doi:
     data=next((r for r in data.get('results',[]) if SequenceMatcher(None,title.lower(),r.get('display_name','').lower()).ratio()>=.93),{})
    count=data.get('cited_by_count')
   if isinstance(count,int) and not isinstance(count,bool) and count>=0:
    candidate={'citation_count':count,'citation_source':source,'citation_checked':time.time()}
    if result is None or count>result['citation_count']:result=candidate
    if count>0:break
  except Exception:continue
 with LOCK:
  if len(CACHE)>1000:CACHE.clear()
  CACHE[key]=(time.time(),result)
 return result
def enrich(items):
 targets=[i for i in items if i.get('type')=='papers' and not i.get('citation_count')][:60]
 pool=concurrent.futures.ThreadPoolExecutor(max_workers=6)
 work={pool.submit(lookup,i.get('doi',''),i['title']):i for i in targets}
 done,pending=concurrent.futures.wait(work,timeout=20)
 for future in done:
  try:data=future.result()
  except Exception:data=None
  if data:work[future].update(data)
 for future in pending:future.cancel()
 pool.shutdown(wait=False,cancel_futures=True)
 return items
