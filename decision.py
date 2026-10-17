"""Guided decision reports: explicitly separate evidence, proposals and uncertainties."""
import concurrent.futures,json,re,secrets,threading,time
from pathlib import Path
import knowledge,fusion
JOBS={};LOCK=threading.RLock();POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
TEMPLATES={'专题分析':['问题与目标','现状与证据','关键问题与原因','可选路径与利弊','建议与实施步骤','风险与待核实事项'],'决策比较':['决策背景与约束','评价维度','方案比较','建议选择与适用条件','实施计划','风险与待核实事项'],'调研报告':['调研背景与范围','材料反映的现状','主要发现','经验与启示','工作建议','资料局限与后续调研']}

def validate(body):
 kind=body.get('kind','专题分析')
 if kind not in TEMPLATES:raise ValueError('请选择报告类型。')
 title=str(body.get('title','')).strip();context=str(body.get('context','')).strip()
 if not 2<=len(title)<=150:raise ValueError('请输入2至150字的分析主题。')
 if not 10<=len(context)<=6000:raise ValueError('请用10至6000字描述背景、现状或需要解决的问题。')
 ids=body.get('file_ids',[])
 if not isinstance(ids,list) or len(ids)>12 or any(not isinstance(i,str) or i not in knowledge.UPLOADS for i in ids):raise ValueError('所选材料已失效，请重新导入。')
 outline=body.get('outline',TEMPLATES[kind])
 if not isinstance(outline,list) or not 3<=len(outline)<=10 or any(not isinstance(x,str) or not 2<=len(x.strip())<=80 for x in outline):raise ValueError('报告结构需有3至10个章节，每个标题2至80字。')
 return {'kind':kind,'title':title,'context':context,'audience':str(body.get('audience','项目负责人'))[:200],'constraints':str(body.get('constraints',''))[:2000],'goals':str(body.get('goals',''))[:2000],'outline':[x.strip() for x in outline],'file_ids':list(dict.fromkeys(ids))}

def start(body,model,extract,storage):
 brief=validate(body)
 with LOCK:
  if any(j['status']=='running' for j in JOBS.values()):raise ValueError('已有报告正在生成，请等待完成。')
  if len(JOBS)>=15:JOBS.pop(next((i for i,j in JOBS.items() if j['status']!='running'),next(iter(JOBS))))
  identity=secrets.token_urlsafe(16);job={'id':identity,'status':'running','progress':2,'message':'正在准备分析材料…','created':time.time(),'title':brief['title'],'brief':brief,'files':[],'chunks':[],'sections':[],'issues':[]};JOBS[identity]=job
 POOL.submit(run,job,model,extract,storage)
 return {'id':identity}

def run(job,model,extract,storage):
 try:
  brief=job['brief'];provided='分析主题：'+brief['title']+'\n用户提供的背景：'+brief['context']+'\n目标：'+brief['goals']+'\n约束：'+brief['constraints']
  chunks=[{'id':'U1-P1','file_id':'U1','path':'用户提供的背景与要求','kind':'用户输入（未独立核验）','paragraph':1,'text':provided}];files=[{'id':'U1','path':'用户提供的背景与要求','kind':'用户输入（未独立核验）'}]
  uploads=[dict(knowledge.UPLOADS[i]) for i in brief['file_ids']]
  def read(upload):
   text=extract(Path(upload['path'])).strip()
   if not text:raise ValueError('没有提取到文字')
   if len(text)>120000:raise ValueError('内容超过12万字符，请拆分材料')
   return text
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
   futures=[pool.submit(read,u) for u in uploads];total=0
   for index,(u,future) in enumerate(zip(uploads,futures),1):
    try:text=future.result()
    except Exception as e:job['issues'].append(u['name']+'：'+str(e));continue
    if total+len(text)>300000:job['issues'].append(u['name']+'：超过本批30万字符容量，未纳入');continue
    total+=len(text);fid='D'+str(index);files.append({'id':fid,'path':u['name'],'kind':'参考材料'})
    for block in text.splitlines():
     if not block.strip():continue
     for offset in range(0,len(block),1600):
      number=sum(c['file_id']==fid for c in chunks)+1;chunks.append({'id':fid+'-P'+str(number),'file_id':fid,'path':u['name'],'kind':'参考材料','paragraph':number,'continuation':offset>0,'text':block[offset:offset+1600]})
    job.update(progress=5+round(index/max(1,len(uploads))*20),message=f'已读取 {index} / {len(uploads)} 份材料')
  if uploads and len(files)==1:raise ValueError('所选材料均未读取成功，请检查文件；不会静默生成无材料报告。')
  job.update(files=files,chunks=chunks)
  facts=[];batches=[];batch=[];size=0
  for c in chunks:
   if batch and size+len(c['text'])>18000:batches.append(batch);batch=[];size=0
   batch.append(c);size+=len(c['text'])
  if batch:batches.append(batch)
  if len(batches)>1:
   def summarize(part):
    result=fusion.prompt('围绕分析需求提取最多12条关键事实，返回facts:[{text,citations:[{id,quote}]}]。每条引用必须逐字摘录，15至70字。提取矛盾和缺口，不写建议。',{'requirements':brief,'paragraphs':part},model)
    valid=fusion.grounded(result.get('facts',[]),part)
    if not valid:raise ValueError('一组材料未返回有效引用，请重试。')
    return valid,False
   for values in fusion.parallel_stage(job,'提取材料证据',[(f'材料组 {i+1}',lambda part=part:summarize(part)) for i,part in enumerate(batches)],25,60):facts.extend(values)
  job.update(progress=65,message='正在组织分析、比较方案与核对依据…')
  prompt='你是高校管理与研究的辅助分析助手。根据需求生成可读的中文报告，遵循outline顺序，输出sections:[{title,claims:[{text,kind,citations:[{id,quote}]}]}]和questions数组。kind只能是fact（材料事实，必须有原文引用）、proposal（分析建议，不声称已经实施或必然有效）、uncertainty（待核实信息）。每条text用完整连贯段落表达，最多18条，总计1500字以内。不得虚构统计数据、调研样本、政策效力、案例或已完成的成果。用户输入是用户自述，不代表独立核验；未提供外部材料时，只能生成分析框架与建议稿，明确资料缺口。方案比较需交代适用条件、资源需求、风险与下一步。quote须逐字摘录，不超过70字。仅返回JSON。'
  data=fusion.prompt(prompt,{'requirements':brief,'facts':facts} if facts else {'requirements':brief,'paragraphs':chunks},model,require_citations=False)
  sections=[];dropped=0
  for section in data.get('sections',[]) if isinstance(data.get('sections'),list) else []:
   if not isinstance(section,dict):continue
   claims=[]
   for claim in section.get('claims',[]) if isinstance(section.get('claims'),list) else []:
    if not isinstance(claim,dict) or not isinstance(claim.get('text'),str):continue
    kind=claim.get('kind','fact');valid=fusion.grounded([claim],chunks)
    if kind=='fact' and not valid:dropped+=1;continue
    if kind not in ('fact','proposal','uncertainty'):dropped+=1;continue
    claims.append({'text':claim['text'][:3500],'kind':kind,'citations':valid[0]['citations'] if valid else []})
   if claims:sections.append({'title':str(section.get('title','分析'))[:100],'claims':claims})
  if not sections:raise ValueError('报告未取得可用分析或有效引用，请补充材料后重试。')
  if dropped:job['issues'].append(str(dropped)+'条未通过引用或格式核对的内容已移除。')
  cited={r['id'].split('-P')[0] for s in sections for c in s['claims'] for r in c['citations']}
  for f in files:
   if f['id'] not in cited and f['id']!='U1':job['issues'].append(f['path']+'：已读取，但成稿未引用，请核对覆盖范围。')
  job.update(sections=sections,questions=[q[:200] for q in data.get('questions',[]) if isinstance(q,str)][:5],basis='材料支持的分析草稿' if uploads else '仅基于用户描述的分析框架与建议稿',progress=95,message='正在保存报告…')
  storage.mkdir(parents=True,exist_ok=True);saved=dict(job,status='done',progress=100,message='分析报告已保存，请核对依据与建议。');temp=storage/(job['id']+'.tmp');temp.write_text(json.dumps(saved,ensure_ascii=False),'utf-8');temp.replace(storage/(job['id']+'.json'));job.update(saved)
 except Exception as e:job.update(status='error',message=str(e) if isinstance(e,ValueError) else '本次报告生成失败，请重试。')

def get(body,storage):
 identity=body.get('id','')
 if not isinstance(identity,str) or not re.fullmatch('[A-Za-z0-9_-]{10,40}',identity):raise ValueError('报告编号无效。')
 if identity in JOBS:return JOBS[identity]
 path=storage/(identity+'.json')
 if not path.is_file():raise ValueError('报告不存在。')
 return json.loads(path.read_text('utf-8'))

def status(body,storage):
 with LOCK:return json.loads(json.dumps({k:v for k,v in get(body,storage).items() if k!='chunks'},ensure_ascii=False))
def reports(storage):return fusion.reports(storage)
def source(body,storage):
 job=get(body,storage);part=next((c for c in job['chunks'] if c['id']==body.get('source_id')),None)
 if not part:raise ValueError('引用不存在。')
 return dict(part,paragraphs=[c for c in job['chunks'] if c['file_id']==part['file_id']],file=next(f for f in job['files'] if f['id']==part['file_id']))
