"""Evidence-backed, bounded multi-hop graph from user-selected local documents."""
import copy,functools
import base64,concurrent.futures,hashlib,json,re,secrets,threading,time,urllib.parse,urllib.request
from pathlib import Path
from difflib import SequenceMatcher
import evidence,research,fusion
UPLOADS={};JOBS={};LOCK=threading.RLock();POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1);CACHE={}
DOI_RE=r'10\.\d{4,9}/[-._;()/:A-Z0-9]+'

MEMO={};INFLIGHT={};CACHE_TAG=lambda:''
def memoized(fn):
 @functools.wraps(fn)
 def wrapped(*args,**kwargs):
  values=args
  if fn.__name__=='resolve_reference':values=(args[0].get('title',''),args[0].get('doi',''))
  if fn.__name__=='extract_refs':values=(args[0],args[1],bool(args[2]) if len(args)>2 else False,CACHE_TAG())
  identity=(fn.__name__,hashlib.sha256(repr((values,kwargs)).encode()).hexdigest())
  with LOCK:
   hit=MEMO.get(identity)
   if hit and time.monotonic()<hit[0]:return copy.deepcopy(hit[1])
   future=INFLIGHT.get(identity);owner=future is None
   if owner:future=concurrent.futures.Future();INFLIGHT[identity]=future
  if not owner:return copy.deepcopy(future.result())
  try:
   value=fn(*args,**kwargs)
   with LOCK:
    if len(MEMO)>500:MEMO.pop(next(iter(MEMO)))
    MEMO[identity]=(time.monotonic()+(3600 if value else 120),copy.deepcopy(value))
   future.set_result(value);return copy.deepcopy(value)
  except Exception as e:future.set_exception(e);raise
  finally:
   with LOCK:INFLIGHT.pop(identity,None)
 return wrapped

def doi(value):
 m=re.search(DOI_RE,value,re.I)
 return m[0].rstrip('.,;)').lower() if m else ''

def key(value):return re.sub(r'[^a-z0-9\u4e00-\u9fff]','',value.lower())

def request(url):
 with LOCK:cached=CACHE.get(url)
 if cached and time.time()-cached[0]<3600:return cached[1]
 result=json.loads(research.fetch(url))
 with LOCK:
  if len(CACHE)>600:CACHE.clear()
  CACHE[url]=(time.time(),result)
 return result

def upload(body,storage,supported):
 name=str(body.get('name',''));suffix=Path(name).suffix.lower()
 if suffix not in supported:raise ValueError('此文件暂时不能读取，请选择 PDF、Word、Excel、文本或图片。')
 try:raw=base64.b64decode(body.get('data',''),validate=True)
 except Exception:raise ValueError('文件传输不完整，请重新选择。')
 if not raw or len(raw)>15_000_000:raise ValueError('每个文件需在 15 MB 以内。')
 name=Path(name.replace('\\','/')).name[:180];identity=secrets.token_urlsafe(16);storage.mkdir(parents=True,exist_ok=True)
 with LOCK:
  if len(UPLOADS)>=300:raise ValueError('本次运行已导入300份文件，请重启应用后继续。')
  path=storage/(identity+suffix);path.write_bytes(raw);UPLOADS[identity]={'id':identity,'name':name,'path':str(path),'size':len(raw)}
 return {'id':identity,'name':name,'size':len(raw)}

def start(body,model,extract):
 ids=body.get('file_ids',[])
 if not isinstance(ids,list) or not 1<=len(ids)<=60 or any(not isinstance(i,str) or i not in UPLOADS for i in ids):raise ValueError('请选择1至60个已导入文件。')
 try:depth=int(body.get('depth',1));fanout=int(body.get('fanout',6))
 except (TypeError,ValueError):raise ValueError('拓展层数或每层数量无效。')
 if not 1<=depth<=4 or not 2<=fanout<=12:raise ValueError('层数需为1至4，每个节点拓展2至12条。')
 with LOCK:
  if any(j['status']=='running' for j in JOBS.values()):raise ValueError('已有图谱正在生成，请等待完成。')
  if len(JOBS)>=12:JOBS.pop(next(iter(JOBS)))
  identity=secrets.token_urlsafe(16);job={'id':identity,'status':'running','progress':0,'message':'正在读取文件…','created':time.time(),'depth':depth,'fanout':fanout,'nodes':[],'edges':[],'warnings':[]};JOBS[identity]=job
 POOL.submit(run,job,[dict(UPLOADS[i]) for i in dict.fromkeys(ids)],model,extract)
 return {'id':identity}

def status(body):
 with LOCK:
  job=JOBS.get(body.get('id'))
  if not job:raise ValueError('图谱任务已过期，请重新生成。')
  return {k:json.loads(json.dumps(v,ensure_ascii=False)) for k,v in job.items() if not k.startswith('_')}

@memoized
def metadata(title='',identifier=''):
 if identifier:
  try:
   r=request('https://api.openalex.org/works/https://doi.org/'+urllib.parse.quote(identifier,safe=''))
   return from_openalex(r)
  except Exception:pass
 try:
  if identifier:r=request('https://api.crossref.org/works/'+urllib.parse.quote(identifier,safe=''))['message']
  else:
   rows=request('https://api.crossref.org/works?'+urllib.parse.urlencode({'query.title':title,'rows':3}))['message']['items'];r=next((r for r in rows if SequenceMatcher(None,key(title),key(' '.join(r.get('title',[])))).ratio()>=.88),None)
   if not r:return None
  identifier=r['DOI'].lower();return {'id':'doi:'+identifier,'doi':identifier,'title':' '.join(r.get('title',[])) or title,'url':'https://doi.org/'+identifier,'type':'papers','citation_count':r.get('is-referenced-by-count'),'source':'Crossref','date':'-'.join(map(str,r.get('published',{}).get('date-parts',[[]])[0])),'authors':'、'.join(' '.join([a.get('given',''),a.get('family','')]) for a in r.get('author',[])[:5]),'pdf_url':next((l['URL'] for l in r.get('link',[]) if l.get('content-type')=='application/pdf'),''),'_crossref':r}
 except Exception:return None

def from_openalex(r):
 d=doi(r.get('doi') or '');oa=r['id'].rsplit('/',1)[-1];loc=r.get('best_oa_location') or r.get('primary_location') or {}
 return {'id':'doi:'+d if d else 'oa:'+oa,'doi':d,'oa':oa,'title':r.get('display_name','未命名文献'),'url':r.get('doi') or loc.get('landing_page_url') or r['id'],'type':'papers','date':r.get('publication_date',''),'authors':'、'.join(a.get('author',{}).get('display_name','') for a in r.get('authorships',[])[:5]),'citation_count':r.get('cited_by_count'),'source':'OpenAlex','pdf_url':loc.get('pdf_url') or '', '_openalex':r}

def unresolved(ref):
 return {'id':'ref:'+hashlib.sha256(key(ref['title']).encode()).hexdigest()[:20],'title':ref['title'],'doi':ref.get('doi',''),'url':'','type':'policy' if re.search('办法|条例|意见|通知',ref['title']) else 'reference','source':'原文明确提及；外部元数据未确认','citation_count':None}

@memoized
def resolve_reference(ref):
 title=ref['title'];is_policy=bool(re.search('办法|条例|意见|通知|规定|方案',title))
 if not is_policy:
  meta=metadata(title,ref.get('doi',''))
  if meta:return meta
 if len(title)>=6:
  try:
   for r in research.web_candidates('"'+title+'"')[:2]:
    if evidence.landing_page(r['url'],r['title']):continue
    try:a=evidence.read_article(r['url'])
    except Exception:continue
    if title not in a['title'] and SequenceMatcher(None,key(title),key(a['title'])).ratio()<.85:continue
    return {'id':'web:'+hashlib.sha256(a['url'].encode()).hexdigest()[:20],'title':a['title'],'url':a['url'],'type':'policy' if is_policy else 'news','date':a.get('date',''),'source':'已读取网页原文','citation_count':None,'_text':a['text']}
  except Exception:pass
 return None

def neighbors(n,limit):
 result=[];notes=[]
 if not n.get('doi') and not n.get('oa') and n.get('_text'):
  for title in list(dict.fromkeys(re.findall(r'《([^》\n]{4,160})》',n['_text'])))[:limit]:
   if key(title)==key(n['title']):continue
   ref={'title':title,'doi':''};target=resolve_reference(ref) or unresolved(ref);result.append((target,'mention','原文明确提及：《'+title+'》'))
 if n.get('doi') or n.get('oa'):
  try:
   r=n.get('_openalex') or request('https://api.openalex.org/works/'+(n['oa'] if n.get('oa') else 'https://doi.org/'+urllib.parse.quote(n['doi'],safe='')))
   targets=[x.rsplit('/',1)[-1] for x in r.get('referenced_works',[])[:limit]]
   if targets:
    data=request('https://api.openalex.org/works?'+urllib.parse.urlencode({'filter':'openalex:'+'|'.join(targets),'per-page':limit}))
    result.extend((from_openalex(x),'out','OpenAlex 收录参考文献') for x in data.get('results',[]))
   data=request('https://api.openalex.org/works?'+urllib.parse.urlencode({'filter':'cites:'+r['id'].rsplit('/',1)[-1],'per-page':limit,'sort':'cited_by_count:desc'}))
   result.extend((from_openalex(x),'in','OpenAlex 收录引用本文的文献') for x in data.get('results',[]))
   return result,notes
  except Exception:notes.append('部分 OpenAlex 引文未取得，尝试备用数据库。')
  if n.get('doi'):
   try:
    r=n.get('_crossref') or request('https://api.crossref.org/works/'+urllib.parse.quote(n['doi'],safe=''))['message']
    for ref in r.get('reference',[]):
     d=doi(ref.get('DOI',''))
     if not d:continue
     result.append(({'id':'doi:'+d,'doi':d,'title':ref.get('article-title') or ref.get('unstructured') or d,'url':'https://doi.org/'+d,'type':'papers','citation_count':None,'source':'Crossref 参考文献'},'out','Crossref 收录参考文献'))
     if len(result)>=limit:break
   except Exception:notes.append('Crossref 参考文献暂不可用。')
   notes.append('未取得完整反向引用，不代表无人引用。')
 return result,notes

@memoized
def extract_refs(text,title,model):
 refs=[]
 for m in re.finditer(r'《([^》\n]{4,160})》',text):refs.append({'title':m[1],'quote':m[0],'doi':'','relation':'mention'})
 # Only use DOI occurrences after the explicit references heading for outgoing edges.
 reference=re.search(r'(?:参考文献|References|Bibliography)\s*[:：]?\s*\n',text,re.I)
 if reference:
  for line in text[reference.end():].splitlines():
   d=doi(line)
   if d:refs.append({'title':line[:200],'quote':line[:500],'doi':d,'relation':'citation'})
 if model:
  sample=text[:12000]+('\n'+text[-16000:] if len(text)>12000 else '')
  try:
   data=fusion.prompt('从材料识别真实标题及明确引用的文献、政策、新闻资讯。输出title、title_quote及references:[{title,quote,doi,relation}]，至多10项，quote必须逐字摘录给定原文且含完整title，relation为citation或mention。不要把主题相近当引用，不得生成网址。不能确认的字段为空。',{'filename':title,'text':sample},model)
   t=str(data.get('title','')).strip();q=str(data.get('title_quote',''))
   if len(t)>4 and t in q and q in sample:title=t[:300]
   for r in data.get('references',[]) if isinstance(data.get('references'),list) else []:
    if not isinstance(r,dict):continue
    t=str(r.get('title','')).strip();q=str(r.get('quote','')).strip();d=doi(str(r.get('doi','')))
    if len(t)>=4 and len(q)>=6 and t in q and q in sample:refs.append({'title':t[:300],'quote':q[:1200],'doi':d if d and d in q.lower() else '','relation':'citation' if r.get('relation')=='citation' else 'mention'})
  except Exception:pass
 return title,list({key(r['title']):r for r in refs}.values())[:30]

def run(job,files,model,extract):
 nodes={};edges={};private={};warnings=[];deadline=time.monotonic()+600
 def add(n,level=0,seed=False):
  identity=n['id']
  if identity not in nodes and len(nodes)>=120:return None
  existing=nodes.get(identity,{})
  merged=dict(existing,**n);merged['level']=min(level,existing.get('level',level));merged['seed']=seed or existing.get('seed',False)
  for k in list(merged):
   if k.startswith('_'):private.setdefault(identity,{})[k]=merged.pop(k)
  nodes[identity]=merged;return identity
 def edge(a,b,kind,proof):
  if a and b and a!=b:
   old=edges.get((a,b))
   if not old or (old['kind']=='mention' and kind=='citation'):edges[(a,b)]={'source':a,'target':b,'kind':kind,'evidence':proof}
 def publish(message,progress):
  counts={i:set() for i in nodes}
  for e in edges.values():counts[e['source']].add(e['target']);counts[e['target']].add(e['source'])
  with LOCK:
   job.update(message=message,progress=progress,nodes=[dict(n,degree=len(counts[i]),download='original' if private.get(i,{}).get('_path') else 'pdf' if n.get('pdf_url') else 'text' if private.get(i,{}).get('_text') else '') for i,n in nodes.items()],edges=list(edges.values()),warnings=list(dict.fromkeys(warnings)),_nodes={i:dict(n,**private.get(i,{})) for i,n in nodes.items()})
 try:
  seeds=[];refs_by_seed={}
  def read(f):
   text=extract(Path(f['path']))
   if len(text)>180000:raise ValueError('文件文本超过18万字符，请拆分后导入。')
   title,refs=extract_refs(text,Path(f['name']).stem,model)
   # Do not mistake a reference-list DOI for the document's own DOI.
   front=re.split(r'参考文献|References|Bibliography',text[:3000],flags=re.I)[0]
   own=doi(front) if re.search(r'(?:doi\s*[:：]|https?://(?:dx\.)?doi.org/)',front,re.I) else ''
   meta=metadata(title,own) if own else None if re.search('会议纪要|工作记录|工作报告|办法|条例|通知|规定',title) else metadata(title)
   return text,title,refs,meta
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   tasks={pool.submit(read,f):f for f in files}
   for complete,future in enumerate(concurrent.futures.as_completed(tasks),1):
    f=tasks[future]
    try:text,title,refs,meta=future.result()
    except Exception as e:warnings.append(f['name']+'：'+str(e));continue
    n=meta or {'id':'local:'+f['id'],'title':title,'type':'policy' if re.search('办法|通知|意见|规定|条例',title) else 'document','url':'','source':'本地材料','citation_count':None}
    n.update(filename=f['name'],_path=f['path'],_name=f['name'],_text=text);identity=add(n,0,True);seeds.append(identity);refs_by_seed[identity]=refs
    publish(f'已读取 {complete} / {len(files)} 份材料',round(20*complete/len(files)))
  if not seeds:raise ValueError('没有可读取的文件，请检查材料后重试。')
  # Match references across all uploaded files before resolving remote metadata.
  for identity in seeds:
   text=private[identity]['_text']
   for other in seeds:
    if other!=identity and len(nodes[other]['title'])>=6 and nodes[other]['title'] in text:edge(identity,other,'mention',nodes[other]['title'])
  work=[(identity,ref) for identity in seeds for ref in refs_by_seed[identity][:job['fanout']]]
  publish('正在核对原文中的引用与外部来源…',22)
  known_titles={key(n['title']):dict(n) for n in nodes.values()}
  def resolve_known(ref):return known_titles.get(key(ref['title'])) or resolve_reference(ref)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   tasks={pool.submit(resolve_known,ref): (identity,ref) for identity,ref in work}
   for future in concurrent.futures.as_completed(tasks):
    identity,ref=tasks[future];matched=next((i for i,n in nodes.items() if key(n['title'])==key(ref['title'])),None)
    if not matched:
     try:meta=future.result()
     except Exception:meta=None
     matched=add(meta or unresolved(ref),1)
    edge(identity,matched,ref['relation'],ref['quote'])
  # Web reverse mentions for non-DOI seed documents: exact title + full text proof.
  def reverse_mentions(identity):
   n=nodes[identity];found=[]
   if n.get('doi') or time.monotonic()>deadline:return found
   for r in research.web_candidates('"'+n['title']+'"')[:4]:
    if time.monotonic()>deadline:break
    if evidence.landing_page(r['url'],r['title']):continue
    try:a=evidence.read_article(r['url'])
    except Exception:continue
    if n['title'] in a['text'] and key(a['title'])!=key(n['title']):found.append(a)
   return found
  reverse_seeds=[i for i in seeds if not nodes[i].get('doi')]
  if reverse_seeds:publish('正在并行核对网页反向提及…',24)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   tasks={pool.submit(reverse_mentions,i):i for i in reverse_seeds}
   for future in concurrent.futures.as_completed(tasks):
    identity=tasks[future]
    try:articles=future.result()
    except Exception:warnings.append('部分网页反向提及检索不可用。');continue
    for a in articles:
     other=add({'id':'web:'+hashlib.sha256(a['url'].encode()).hexdigest()[:20],'title':a['title'],'url':a['url'],'date':a.get('date',''),'type':'policy' if re.search('办法|条例|意见|通知',a['title']) else 'news','source':'网页正文明确提及','citation_count':None,'_text':a['text']},1)
     edge(other,identity,'mention',nodes[identity]['title'])
  frontier=list(seeds);expanded=set()
  for level in range(job['depth']):
   if time.monotonic()>deadline:warnings.append('已达到本次处理时限，保留已取得关系。');break
   current=[i for i in frontier if i not in expanded and nodes[i]['level']<job['depth']][:24-len(expanded)]
   if not current:break
   next_frontier=[]
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    tasks={pool.submit(neighbors,dict(nodes[i],**private.get(i,{})),job['fanout']):i for i in current}
    for future in concurrent.futures.as_completed(tasks):
     identity=tasks[future];expanded.add(identity)
     try:found,notes=future.result();warnings.extend(notes)
     except Exception:found=[];warnings.append('部分引用数据库连接失败。')
     for n,direction,proof in found:
      other=add(n,nodes[identity]['level']+1)
      if other:
       if direction in ('out','mention'):edge(identity,other,'mention' if direction=='mention' else 'citation',proof)
       else:edge(other,identity,'citation',proof)
       next_frontier.append(other)
     publish(f'正在拓展第 {level+1} / {job["depth"]} 层 · {len(nodes)} 个节点',25+round(60*(level+len(expanded)/max(1,len(expanded)+len(current)))/job['depth']))
   frontier=list(dict.fromkeys(next_frontier+[i for i,n in nodes.items() if n['level']==level+1]))
  pending=[(i,n) for i,n in nodes.items() if not n.get('seed') and (not n.get('url') or n.get('source')=='Crossref 参考文献')][:24]
  if pending and time.monotonic()<deadline:
   publish('正在核验关联文件与可访问来源链接…',94)
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    checks={pool.submit(resolve_reference,{'title':n['title'],'doi':n.get('doi','')}):i for i,n in pending}
    for future in concurrent.futures.as_completed(checks):
     identity=checks[future]
     try:verified=future.result()
     except Exception:verified=None
     if verified:
      verified['id']=identity;add(verified,nodes[identity]['level'])
  for identity,n in nodes.items():
   n['verification']='local' if private.get(identity,{}).get('_path') else 'verified_text' if private.get(identity,{}).get('_text') and n.get('url') else 'verified_metadata' if n.get('source') in ('OpenAlex','Crossref') and n.get('url') else 'reference_record' if n.get('url') else 'unverified'
   if n['verification']=='unverified':n['search_url']='https://www.bing.com/search?'+urllib.parse.urlencode({'q':'"'+n['title']+'"'})
  if len(expanded)>=24 or len(nodes)>=120:warnings.append('达到本次24个拓展节点或120个总节点上限，图谱为部分网络。')
  warnings.append('箭头从引用方指向被引用方；虚线为原文明确提及。节点大小表示本图连接数，不是全网影响力。数据库未收录或获取失败的关系无法展示。')
  publish('图谱已生成',100)
  with LOCK:job['status']='done'
 except Exception as e:
  publish('图谱生成未完成',job.get('progress',0))
  with LOCK:job.update(status='error',message=str(e) if isinstance(e,ValueError) else '图谱生成失败，请重试。')

def download(body):
 with LOCK:
  job=JOBS.get(body.get('id'));n=job.get('_nodes',{}).get(body.get('node_id')) if job else None
 if not n:raise ValueError('节点不存在，请重新生成图谱。')
 if n.get('_path'):return Path(n['_path']).read_bytes(),n.get('_name','材料')
 if n.get('pdf_url'):
  url=evidence.public_url(n['pdf_url']);req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.build_opener(evidence.Redirect()).open(req,timeout=20) as r:raw=r.read(15_000_001)
  if len(raw)>15_000_000 or not raw.startswith(b'%PDF'):raise ValueError('未取得可下载 PDF，请访问原始来源。')
  return raw,n['title'][:100]+'.pdf'
 if n.get('_text'):return n['_text'].encode('utf-8-sig'),n['title'][:100]+'.txt'
 raise ValueError('此节点尚无可公开下载的文件，可访问来源；不会把资料卡当作原文件。')
