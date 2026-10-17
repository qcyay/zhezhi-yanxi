let researchStep=0, researchBusy=false, researchJob=null, pollTimer=null;
const researchBrief={topic:'',purpose:'专题调研',types:['papers','policy','news'],scope:'国内外高校',period:'5',notes:'',policy_levels:['国家','教育部','其他部委','省市','高校'],include_older_policies:true,use_local_policies:true};
const typeLabels={papers:'学术文献',policy:'政策与官方文件',news:'新闻信息'};
let previewEpoch=0;
let researchResultItems=[];
const researchQuestions=[
 {title:'你想研究什么主题？',hint:'可以输入一个关键词，也可以直接描述你希望解决的问题。',field:'topic',choices:['数据治理','高校数字化转型','人工智能赋能管理','学科建设'],placeholder:'例如：高校数据治理的组织机制、数据共享与质量管理'},
 {title:'这次资料主要用来做什么？',hint:'使用目的会影响检索词和后续阅读建议。',field:'purpose',choices:['专题调研','政策制定参考','国内外高校对标','学术研究与综述'],placeholder:'也可以填写具体任务，例如准备数据治理专题汇报'},
 {title:'你希望找到哪些资料？',hint:'可多选。学术文献提供研究线索，官方文件提供政策依据，新闻帮助了解近期动态。',field:'types'},
 {title:'需要关注哪些范围和时间？',hint:'进一步缩小范围，让资料更贴近你的工作。',field:'scope',choices:['国内外高校','国内高校','国外高校','政府与公共管理','不限机构范围'],placeholder:'也可填写具体地区、机构类型或重点高校'},
 {title:'确认需求，开始检索',hint:'模型会扩展检索词，查询公开来源，再根据真实条目整理阅读建议。',field:'review'}
];
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el}
function updateBrief(field,value){researchBrief[field]=value;renderResearchSummary()}
function renderResearchSummary(){
 $('research-brief').replaceChildren();
 const lines=[['主题',researchBrief.topic||'待填写'],['用途',researchBrief.purpose||'待填写'],['资料',researchBrief.types.map(x=>typeLabels[x]).join('、')||'待选择'],['范围',researchBrief.scope||'待填写'],['时间',researchBrief.period==='all'?'不限时间':'近 '+researchBrief.period+' 年']];
 for(const [label,value] of lines){const div=node('div');div.append(node('small',label),node('p',value));$('research-brief').append(div)}
}
function renderResearchStep(){
 const q=researchQuestions[researchStep];$('research-step-label').textContent='步骤 '+(researchStep+1)+' / 5';
 $('research-question').textContent=q.title;$('research-hint').textContent=q.hint;
 $('research-meter').style.width=((researchStep+1)*20)+'%';
 $('research-inputs').replaceChildren();$('research-prev').hidden=researchStep===0;
 $('research-next').textContent=researchStep===4?'开始智能检索 ↗':'下一步 →';
 if(q.choices){const options=node('div',undefined,'choice-options');for(const choice of q.choices){const b=node('button',choice,'choice '+(researchBrief[q.field]===choice?'selected':''));b.type='button';b.onclick=()=>{updateBrief(q.field,choice);renderResearchStep()};options.append(b)}$('research-inputs').append(options);
 const input=node('textarea');input.rows=3;input.maxLength=q.field==='topic'?200:300;input.value=researchBrief[q.field];input.placeholder=q.placeholder;input.setAttribute('aria-label',q.title);input.oninput=()=>{updateBrief(q.field,input.value);options.querySelectorAll('button').forEach(b=>b.classList.toggle('selected',b.textContent===input.value))};$('research-inputs').append(input)}
 if(q.field==='types'){for(const [value,label,detail] of [['papers','学术文献','通过 Crossref 获取标题、作者、DOI 与可用摘要'],['policy','政策与官方文件','查找公开政策，并核验正文与研究主题'],['news','新闻信息','查找具体报道与动态，提取文章内容和发布时间']]){const labelEl=node('label',undefined,'type-choice');const input=node('input');input.type='checkbox';input.checked=researchBrief.types.includes(value);input.onchange=()=>{updateBrief('types',input.checked?[...researchBrief.types,value]:researchBrief.types.filter(t=>t!==value))};const text=node('div');text.append(node('strong',label),node('p',detail));labelEl.append(input,text);$('research-inputs').append(labelEl)}}
 if(q.field==='scope'){const label=node('label','资料时间范围','field-label');const select=node('select');select.setAttribute('aria-label','资料时间范围');for(const [value,text] of [['3','近 3 年'],['5','近 5 年'],['10','近 10 年'],['all','不限时间']]){const option=node('option',text);option.value=value;select.append(option)}select.value=researchBrief.period;select.onchange=()=>updateBrief('period',select.value);label.append(select);$('research-inputs').append(label,node('p','按可提取的发布日期筛选；未确认日期的政策会明确标注，新闻需有发布日期。','hint'))}
 if(q.field==='review'){const label=node('label','还有其他偏好吗？（选填）','field-label');const input=node('textarea');input.rows=3;input.maxLength=1500;input.value=researchBrief.notes;input.placeholder='例如：优先关注数据标准、组织保障，排除医疗行业案例';input.oninput=()=>updateBrief('notes',input.value);label.append(input);$('research-inputs').append(label,node('p','检索需求与候选资料元数据会发送至已配置的大模型；检索词会发送至公开检索服务。采用设置中当前模型。','hint'))}
 renderResearchSummary();
}
$('research-prev').onclick=()=>{researchStep=Math.max(0,researchStep-1);renderResearchStep()};
$('research-next').onclick=async()=>{
 if(researchStep===0&&researchBrief.topic.trim().length<2)return toast('请输入至少两个字的研究主题');
 if(researchStep===1&&!researchBrief.purpose.trim())return toast('请选择或填写使用目的');
 if(researchStep===2&&!researchBrief.types.length)return toast('请至少选择一种资料类型');
 if(researchStep===3&&!researchBrief.scope.trim())return toast('请选择或填写研究范围');
 if(researchStep<4){researchStep++;renderResearchStep();return}
 if(!configured){openSettings();toast('请先保存 API Key，再开始智能检索');return}
 if(researchBusy)return;
 researchBusy=true;$('research-next').disabled=true;$('research-results').hidden=true;$('research-progress').hidden=false;$('research-progress-text').textContent='正在创建检索任务…';$('research-poll-retry').hidden=true;
 try{const data=await api('research/start',researchBrief);researchJob=data.id;$('research-wizard').hidden=true;pollResearch()}
 catch(e){researchBusy=false;$('research-next').disabled=false;$('research-progress-text').textContent=e.message;toast(e.message)}
};
async function pollResearch(){
 clearTimeout(pollTimer);
 try{const job=await api('research/status',{id:researchJob});$('research-progress-text').textContent=job.message+(job.status==='running'&&job.created?' · 已用时 '+Math.max(0,Math.floor(Date.now()/1000-job.created))+' 秒':'');$('search-progress-bar').value=job.progress_percent||0;$('progress-percent').textContent=(job.progress_percent||0)+'%';
 const stages=['planning','searching','verifying','organizing','done'];document.querySelectorAll('.research-stage').forEach((el,i)=>el.classList.toggle('reached',i<=stages.indexOf(job.stage)));
 if(job.status==='running'){pollTimer=setTimeout(pollResearch,1200);return}
 researchBusy=false;$('research-next').disabled=false;
 if(job.status==='error'){$('research-wizard').hidden=false;toast(job.message);return}
 renderResearchResults(job);
 }catch(e){$('research-progress-text').textContent='进度连接中断：'+e.message+'。任务可能仍在继续。';$('research-poll-retry').hidden=false}
}
$('research-poll-retry').onclick=()=>{$('research-poll-retry').hidden=true;pollResearch()};
function externalLink(label,url){const link=node('a',label);try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol))return node('span',label)}catch{return node('span',label)}link.href=url;link.target='_blank';link.rel='noopener noreferrer';return link}
function renderResearchResults(job){
 $('research-progress').hidden=false;
 $('research-archive-status').textContent='';previewEpoch++;$('article-preview').classList.remove('is-open');$('preview-body').replaceChildren(node('div','选择左侧资料，在这里阅读内容与匹配依据。','preview-empty'));
 $('research-results').hidden=false;$('research-result-count').textContent=job.items.length+' 条真实来源';$('research-summary').textContent=job.summary;
 $('research-strategy').textContent=job.plan.strategy+'\n\n文献检索词：'+job.plan.paper_queries.join('；')+'\n文件检索词：'+job.plan.policy_queries.join('；')+'\n新闻检索词：'+(job.plan.news_queries||[]).join('；');
 $('research-warnings').replaceChildren(...job.warnings.map(w=>node('p',w)));
 const statuses=(job.sources||[]).map(s=>(s.ok?'已查询':'连接失败')+' · '+typeLabels[s.type]+' · '+s.count+' 条 · '+s.query);$('research-source-status').textContent=statuses.join('\n')+'\n\n候选 '+(job.candidate_count??job.items.length)+' 条，已排除 '+(job.excluded||[]).length+' 条。\n'+(job.excluded||[]).map(x=>x.title+'：'+x.reason).join('\n');
 researchResultItems=job.items;$('research-sort').value='relevance';$('research-result-list').replaceChildren();
 for(const item of job.items){const card=node('article',undefined,'result-card');card.dataset.id=item.id;const check=node('input');check.type='checkbox';check.value=item.id;check.setAttribute('aria-label','选择 '+item.title);check.onchange=updateSelected;const heading=node('div',undefined,'result-heading');const title=node('h3');const titleButton=node('button','['+item.id+'] '+item.title);titleButton.onclick=()=>openPreview(item,card);title.append(titleButton);heading.append(check,title);
 const meta=node('p',[typeLabels[item.type],item.source,item.date||'日期待核验',item.date_note,item.publisher,item.authors].filter(Boolean).join(' · '),'result-meta');
 card.append(heading,meta);const facts=node('div',undefined,'result-facts');for(const word of item.keywords||[])facts.append(node('span',word,'keyword'));const rating=node('span','相关度 '+(item.relevance??'—')+'%','relevance');rating.title=item.score_method||'等待评分';facts.append(rating);const impact=node('span','影响力 '+(item.influence?.score==null?'待核验':item.influence.score)+' · '+(item.influence?.label||'数据未知'),'impact');impact.title=item.influence?.basis||'来源未提供可核验指标';facts.append(impact);card.append(facts,node('p',item.reason||item.score_reason||'已通过主题匹配，可查看正文核验。','result-reason'));
 const details=node('details');details.append(node('summary',item.excerpt?'查看来源摘要':'来源未提供摘要'),node('p',item.excerpt||'请访问原始来源阅读全文。'));card.append(details,externalLink('访问原始来源 ↗',item.url));$('research-result-list').append(card)}
 $('research-links').replaceChildren(...(job.links||[]).map(l=>externalLink(l.label+' ↗',l.url)));updateSelected();
}
function selectedResearch(){return [...$('research-result-list').querySelectorAll('input:checked')].map(e=>e.value)}
function updateSelected(){const n=selectedResearch().length;$('research-archive').textContent='归档所选资料卡（'+n+'）';$('research-archive').disabled=!n}
$('research-select-all').onclick=()=>{const checks=[...$('research-result-list').querySelectorAll('input')];const value=!checks.every(c=>c.checked);checks.forEach(c=>c.checked=value);updateSelected()};
$('research-edit').onclick=()=>{$('research-wizard').hidden=false;$('research-results').hidden=true;$('research-progress').hidden=true;researchStep=0;renderResearchStep()};
$('research-archive').onclick=async()=>{const button=$('research-archive');button.disabled=true;try{const result=await api('research/archive',{id:researchJob,ids:selectedResearch()});$('research-archive-status').textContent=result.count+' 份资料卡已归档到当前资料总目录。正在更新资料库…';try{libraryView(await api('scan',{}));$('research-archive-status').textContent=result.count+' 份资料卡已归档并更新索引，可以前往资料问答。'}catch(e){$('research-archive-status').textContent=result.message+' '+e.message}toast(result.message)}catch(e){toast(e.message)}finally{updateSelected()}};
$('research-to-chat').onclick=()=>{show('chat');$('question').value='围绕“'+researchBrief.topic+'”，根据已归档资料梳理主要研究线索，并说明资料不足之处。'};
const sidebar=document.querySelector('.sidebar'), rail=$('sidebar-rail');
function toggleSidebar(open){document.body.classList.toggle('nav-open',open);rail.setAttribute('aria-expanded',String(open));sidebar.inert=!open}
rail.onmouseenter=()=>toggleSidebar(true);rail.onclick=()=>toggleSidebar(true);
sidebar.onmouseleave=()=>{if(!sidebar.contains(document.activeElement))toggleSidebar(false)};
sidebar.addEventListener('focusout',()=>setTimeout(()=>{if(!sidebar.contains(document.activeElement)&&!sidebar.matches(':hover'))toggleSidebar(false)},0));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){toggleSidebar(false);rail.focus()}});
document.addEventListener('pointerdown',e=>{if(!sidebar.contains(e.target)&&!rail.contains(e.target))toggleSidebar(false)});
sidebar.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{toggleSidebar(false);$('main-content').focus()}));
toggleSidebar(false);renderResearchStep();


async function openPreview(item,card){
 const epoch=++previewEpoch;$('article-preview').classList.add('is-open');
 document.querySelectorAll('.result-card').forEach(c=>c.classList.toggle('selected-result',c===card));
 $('preview-body').replaceChildren(node('p','正在读取资料内容…','preview-empty'));
 try{const data=await api('research/preview',{id:researchJob,item_id:item.id});if(epoch!==previewEpoch)return;
 const body=$('preview-body');body.replaceChildren(node('h3',data.title));
 body.append(node('p',[data.content_status,data.date||'日期待核验',data.truncated?'正文因长度限制已截断':''].filter(Boolean).join(' · '),'preview-notice'));
 const facts=node('div',undefined,'result-facts');for(const word of data.keywords||[])facts.append(node('span',word,'keyword'));facts.append(node('span','相关度 '+data.relevance+'%','relevance'));body.append(facts);
 body.append(node('p',data.score_method+'；仅用于排序参考。','preview-notice'),node('div',data.score_reason,'preview-evidence'));
 const toolbar=node('div',undefined,'preview-toolbar');toolbar.append(externalLink('访问原始来源 ↗',data.url));body.append(toolbar);
 const content=node('div',undefined,'preview-content');highlightContent(content,data.content||'来源未提供可读取的摘要或正文，请访问原始来源。',data.keywords||[]);body.append(content);
 body.append(node('p',data.content_status==='数据库摘要（非全文）'?'此处展示数据库摘要，不代表已读取论文全文。':'此处为网页正文的文本提取，版式、图片或附件可能未包含。','preview-notice'));
 }catch(e){if(epoch===previewEpoch)$('preview-body').replaceChildren(node('p',e.message),externalLink('访问原始来源 ↗',item.url))}
}
function highlightContent(parent,text,words){
 const terms=words.filter(w=>typeof w==='string'&&w.length>1).sort((a,b)=>b.length-a.length);
 if(!terms.length){parent.textContent=text;return}
 const lower=text.toLowerCase();let offset=0,count=0;
 while(offset<text.length&&count<300){let best=-1,word='';for(const term of terms){const pos=lower.indexOf(term.toLowerCase(),offset);if(pos>=0&&(best<0||pos<best)){best=pos;word=term}}
 if(best<0)break;parent.append(document.createTextNode(text.slice(offset,best)),node('mark',text.slice(best,best+word.length)));offset=best+word.length;count++}
 parent.append(document.createTextNode(text.slice(offset)));
}
$('close-preview').onclick=()=>{$('article-preview').classList.remove('is-open');previewEpoch++};

$('research-sort').onchange=()=>{const mode=$('research-sort').value,items=[...researchResultItems],value=i=>mode==='influence'?(i.influence?.score??-1):mode==='date'?(Date.parse((i.date||'').replace(/年|月/g,'-').replace('日',''))||-1):(i.relevance??-1);items.sort((a,b)=>value(b)-value(a)||(b.relevance||0)-(a.relevance||0));const cards=new Map([...$('research-result-list').children].map(c=>[c.dataset.id,c]));for(const item of items)if(cards.has(item.id))$('research-result-list').append(cards.get(item.id))};
