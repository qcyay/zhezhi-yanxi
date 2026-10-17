const readingCache=new Map();
function readingKey(path,request){return request.id+'|'+request.item_id+'|'+path+(path==='summary'?'|'+currentModel:'')}
function readingCached(path,request){const key=readingKey(path,request),entry=readingCache.get(key);if(entry&&entry.expires>Date.now())return entry.promise;readingCache.delete(key);const promise=api('research/'+path,request).catch(e=>{readingCache.delete(key);throw e});readingCache.set(key,{promise,expires:Date.now()+30*60*1000});while(readingCache.size>90)readingCache.delete(readingCache.keys().next().value);return promise}
const pdfReadingCache=new Map();
let readerBlob=null;
openPreview=async function(item,card){
 const epoch=++previewEpoch,request={id:researchJob,item_id:item.id};
 if(readerBlob){URL.revokeObjectURL(readerBlob);readerBlob=null}
 $('article-preview').classList.add('is-open');document.querySelectorAll('.result-card').forEach(c=>c.classList.toggle('selected-result',c===card));
 const body=$('preview-body');if(!readingCache.has(readingKey('fulltext',request)))body.replaceChildren(node('h3',item.title),node('p','正在读取完整内容…','reader-loading'));
 try{
 const data=await readingCached('fulltext',request);if(epoch!==previewEpoch)return;
 body.replaceChildren(node('h3',data.title),node('p',[data.content_status,data.date,data.page_count?data.page_count+' 页':'',data.content?data.content.length+' 字符':''].filter(Boolean).join(' · '),'preview-notice'));
 const facts=node('div',undefined,'result-facts');for(const word of data.keywords||[])facts.append(node('span',word,'keyword'));if(typeof data.relevance==='number')facts.append(node('span','相关度 '+data.relevance+'%','relevance'));body.append(facts);
 if(data.fulltext_notice)body.append(node('p',data.fulltext_notice,'preview-evidence'));
 const toolbar=node('div',undefined,'preview-toolbar');if(data.url)toolbar.append(externalLink('访问原始来源 ↗',data.url));if(data.fulltext_url)toolbar.append(externalLink('公开全文 PDF ↗',data.fulltext_url));const refresh=node('button','刷新阅读视图');refresh.onclick=()=>{for(const key of readingCache.keys())if(key.startsWith(request.id+'|'+request.item_id+'|'))readingCache.delete(key);pdfReadingCache.delete(readingKey('pdf',request));openPreview(item,card)};toolbar.append(refresh);body.append(toolbar);
 const textSection=node('section',undefined,'reader-section');textSection.append(node('h4',data.scanned?'完整 PDF 原件':'文章内容'));
 const text=node('div',undefined,'article-fulltext');
 if(!data.scanned){for(const paragraph of (data.content||'来源没有提供可读取文字。').split(/\n\s*\n/)){const p=node('p');highlightContent(p,paragraph,data.keywords||[]);text.append(p)}textSection.append(text)}
 body.append(textSection);
 if(data.local_id){const pdfButton=node('button',data.scanned?'加载扫描 PDF 原件':'查看完整 PDF 原件');toolbar.append(pdfButton);pdfButton.onclick=async()=>{pdfButton.disabled=true;pdfButton.textContent='正在加载 PDF…';try{let blob=pdfReadingCache.get(readingKey('pdf',request));if(!blob){const response=await fetch('/api/research/pdf',{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':token},body:JSON.stringify(request)});if(!response.ok)throw new Error('原件读取失败');blob=await response.blob();pdfReadingCache.set(readingKey('pdf',request),blob);while(pdfReadingCache.size>4)pdfReadingCache.delete(pdfReadingCache.keys().next().value);}if(epoch!==previewEpoch)return;if(readerBlob)URL.revokeObjectURL(readerBlob);readerBlob=URL.createObjectURL(blob);const frame=node('iframe');frame.title=data.title+' 完整 PDF';frame.src=readerBlob;frame.className='reader-pdf';textSection.replaceChildren(node('h4','完整 PDF 原件'),frame);pdfButton.textContent='已加载原件'}catch(e){pdfButton.disabled=false;pdfButton.textContent='重试读取原件';toast(e.message)}};if(data.scanned)pdfButton.click()}
 const summarySection=node('section',undefined,'reader-section');summarySection.append(node('h4','文章总结'));const summaryBody=node('div');summarySection.append(summaryBody);body.append(summarySection);
 const graphSection=node('section',undefined,'reader-section');graphSection.append(node('h4','引用关系与影响力'));const graphBody=node('div');graphSection.append(graphBody);body.append(graphSection);
 async function loadPart(target,path,render){target.replaceChildren(node('p',path==='summary'?'正在根据已读取内容整理文章总结…':'正在查找真实引用关系…','reader-loading'));try{const result=await readingCached(path,request);if(epoch!==previewEpoch)return;target.replaceChildren();render(result,target)}catch(e){if(epoch!==previewEpoch)return;const retry=node('button','重新加载');retry.onclick=()=>loadPart(target,path,render);target.replaceChildren(node('p',e.message,'preview-notice'),retry)}}
 loadPart(summaryBody,'summary',(result,target)=>target.append(node('p',result.text,'article-summary'),node('p','AI 总结依据：'+result.basis,'preview-notice')));
 loadPart(graphBody,'graph',(result,target)=>renderCitationGraph(result,target,request));
 }catch(e){if(epoch===previewEpoch)body.replaceChildren(node('h3',item.title),node('p',e.message),externalLink('访问原始来源 ↗',item.url))}
};
function renderCitationGraph(data,parent,request){
 if(data.nodes.length>9&&!data._paged){const pages=node('div',undefined,'citation-pages'),select=node('select'),plot=node('div');for(let i=0;i<Math.ceil((data.nodes.length-1)/8);i++){const o=node('option','关联组 '+(i+1));o.value=String(i);select.append(o)}pages.append(node('span','分组阅读 · '+(data.nodes.length-1)+' 篇关联资料'),select);parent.append(pages,plot);const draw=()=>{const center=data.nodes.find(n=>n.center),others=data.nodes.filter(n=>!n.center).slice(Number(select.value)*8,Number(select.value)*8+8),nodes=[center,...others],ids=new Set(nodes.map(n=>n.id));plot.replaceChildren();renderCitationGraph({...data,_paged:true,nodes,edges:data.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))},plot,request)};select.onchange=draw;draw();return}
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.classList.add('citation-svg');svg.setAttribute('aria-label','文章引用关系图');
 function el(tag,attrs={}){const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e}
 const center=data.nodes.find(n=>n.center);if(!center){parent.append(node('p','未取得图谱数据'));return}
 const defs=el('defs'),marker=el('marker',{id:'citation-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto'});marker.append(el('path',{d:'M 1 1 L 9 5 L 1 9',fill:'none',stroke:'#92a6c4','stroke-width':1.5}));defs.append(marker);
 for(const [id,light,dark] of [['graph-blue','#ecf3ff','#91add4'],['graph-gold','#fff8e9','#cbb182'],['graph-center','#607eac','#253e64']]){const gradient=el('radialGradient',{id,cx:'30%',cy:'24%',r:'78%'});gradient.append(el('stop',{offset:'0%','stop-color':light}),el('stop',{offset:'100%','stop-color':dark}));defs.append(gradient)}svg.append(defs);
 const incoming=new Set(data.edges.filter(e=>e.target===center.id).map(e=>e.source));const left=data.nodes.filter(n=>!n.center&&!incoming.has(n.id)),right=data.nodes.filter(n=>!n.center&&incoming.has(n.id));
 const positions=new Map(),height=560;svg.setAttribute('viewBox','0 0 600 '+height);
 const radius=n=>n.citation_count==null?15:Math.min(37,16+Math.log2(1+n.citation_count)*3);
 positions.set(center.id,{x:300,y:height/2,r:radius(center)});
 data.nodes.filter(n=>!n.center).forEach((n,i,list)=>{const angle=-Math.PI/2+i*2*Math.PI/list.length;positions.set(n.id,{x:300+Math.cos(angle)*205,y:height/2+Math.sin(angle)*190,r:radius(n)})});
 const edges=[];
 for(const edge of data.edges){const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,x1=a.x+dx*(a.r+3)/d,y1=a.y+dy*(a.r+3)/d,x2=b.x-dx*(b.r+7)/d,y2=b.y-dy*(b.r+7)/d;const path=el('path',{class:'citation-edge',d:`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`,fill:'none',stroke:'#bbcadd','stroke-width':1.3,'marker-end':'url(#citation-arrow)'});svg.append(path);edges.push({path,...edge})}
 const inspector=node('div',undefined,'citation-inspector');inspector.setAttribute('aria-live','polite');inspector.append(node('p','点击任一节点，查看完整标题、被引数及阅读入口。'));
 async function visit(n){if(n.local_id){try{openPreview(await api('research/related',{...request,local_id:n.local_id}))}catch(e){toast(e.message)}}else if(n.url){const link=externalLink('',n.url);if(link.href)window.open(link.href,'_blank','noopener,noreferrer')}}
 function select(n,group){svg.querySelectorAll('.citation-node').forEach(g=>{g.classList.toggle('is-selected',g===group);g.setAttribute('aria-pressed',String(g===group))});for(const e of edges)e.path.style.opacity=e.source===n.id||e.target===n.id?'1':'.22';
  const metric=node('p');metric.append(node('span',n.citation_count==null?'待补充':n.citation_count===0?'暂无记录':String(n.citation_count),'citation-count'),document.createTextNode(n.citation_count==null?'来源未提供被引数':'被引用次数'));
  inspector.replaceChildren(node('h5',n.title),metric,node('p',n.center?'当前阅读的文章':incoming.has(n.id)?'引用本文的资料':'本文引用的资料'),node('p',(n.citation_source?'被引数据：'+n.citation_source+'。':'')+data.count_scope,'preview-notice'));
  if(n.local_id&&!n.center){const button=node('button','阅读这份资料 ↗');button.onclick=()=>visit(n);inspector.append(button)}else if(n.url)inspector.append(externalLink('访问原始来源 ↗',n.url));
 }
 for(const n of data.nodes){const p=positions.get(n.id),group=el('g',{class:'citation-node',tabindex:0,role:'button','aria-pressed':'false','aria-label':'查看 '+n.title});
  const title=el('title');title.textContent=n.title;group.append(title,el('circle',{class:'node-halo',cx:p.x,cy:p.y,r:p.r+8,fill:'none',stroke:n.center?'#849ec4':'#c5d2e4','stroke-width':1,opacity:n.center?.65:0}),el('circle',{class:'node-core',cx:p.x,cy:p.y,r:p.r,fill:'url(#'+(n.center?'graph-center':incoming.has(n.id)?'graph-gold':'graph-blue')+')',stroke:n.center?'#37577f':incoming.has(n.id)?'#bfa271':'#92add1','stroke-width':1.2,'stroke-dasharray':n.citation_count==null?'3 3':'none'}));
  const label=el('text',{x:p.x,y:p.y+p.r+23,'text-anchor':'middle'});const name=n.center?'当前文章':n.title;for(let i=0;i<Math.min(2,Math.ceil(name.length/11));i++){const span=el('tspan',{x:p.x,dy:i?17:0});span.textContent=name.slice(i*11,(i+1)*11)+(i===1&&name.length>22?'…':'');label.append(span)}group.append(label);group.onclick=()=>select(n,group);group.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(n,group)}};svg.append(group)
 }
 const legend=node('div',undefined,'citation-legend');legend.append(node('span','本文引用'),node('span','当前文章'),node('span','引用本文'));
 parent.append(legend,inspector,svg,node('p','圆越大表示被引越多；虚线圆表示被引数未知。箭头指向被引用的文章。','graph-legend'),node('p','数据来源：'+data.source+'。'+data.count_scope,'preview-notice'),node('p',data.message,'preview-notice'));
 const list=node('details');list.append(node('summary','查看关联文章列表（'+(data.nodes.length-1)+'）'));for(const n of data.nodes.filter(n=>!n.center)){const p=node('p');if(n.local_id){const button=node('button',n.title);button.onclick=()=>visit(n);p.append(button)}else p.append(externalLink(n.title,n.url));list.append(p)}parent.append(list);
}

window.addEventListener('beforeunload',()=>{if(readerBlob)URL.revokeObjectURL(readerBlob)});
