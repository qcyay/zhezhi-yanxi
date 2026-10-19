const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name=app-token]').content;
let history = [], busy = false, configured = false, toastTimer, currentModel = "", availableModels = [], modelsLoading = false, modelChanging = false, modelEpoch = 0;
async function api(path, body) {
  const res = await fetch('/api/' + path, {method:body === undefined ? 'GET':'POST', headers:{'Content-Type':'application/json','X-App-Token':token}, body:body === undefined ? undefined:JSON.stringify(body)});
  const data = await res.json(); if (!res.ok) throw Error(data.error || '请求失败'); if(['research/start','decision/start','fusion/start','chat'].includes(path))window.dispatchEvent(new Event('research-interest-updated'));return data;
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000)}
let connectionEpoch=0,bochaEpoch=0;
function bochaState(state,text){const el=$('bocha-status');el.dataset.state=state;el.textContent='● '+text;}
function connectionState(state,text){for(const id of ['api-connection-status','connection']){const el=$(id);el.dataset.state=state;el.textContent='● '+text}}
function configView(s){$('test').disabled=false;connectionEpoch++;connectionState('unknown',s.has_key?'已保存 · 尚未测试':'未配置密钥');$('api-endpoint').value=s.api_endpoint||'https://api.deepseek.com/chat/completions';$('api-provider').value=$('api-endpoint').value.includes('modelgateway.zju.edu.cn')?'zju':$('api-endpoint').value==='https://api.deepseek.com/chat/completions'?'official':'custom';setTimeout(()=>window.prepareRecommendations?.(),1500);if($('directory').value!==s.directory&&window.invalidateRecommendations)window.invalidateRecommendations();bochaEpoch++;bochaState('unknown',s.has_bocha_key?'博查密钥已保存 · 尚未测试':'博查尚未配置');configured=s.has_key;currentModel=s.model;renderModels();$('model').value=s.model;$('directory').value=s.directory;$('policy-directory').value=s.policy_directory||'';$('directory-label').textContent=s.directory;$('key-hint').textContent=s.has_key?'已保存加密密钥。留空可保留，输入新密钥可替换。':'密钥通过 Windows 用户级加密保存在本机。'}
function libraryView(lib){$('library-summary').replaceChildren(document.createTextNode(lib.files.length+' '));const small=document.createElement('small');small.textContent='份资料已读取';$('library-summary').append(small);$('file-list').replaceChildren();for(const file of lib.files){const el=document.createElement('div');el.className='file';el.textContent='▤ '+file.path;$('file-list').append(el)}if(!lib.files.length)$('file-list').textContent='点击“更新”读取本地资料。';$('issues-box').hidden=!lib.issues.length;$('issues').replaceChildren();for(const issue of lib.issues){const el=document.createElement('div');el.textContent=issue;$('issues').append(el)}}
const views={fusion:['项目梳理','整理项目材料、交接工作并追溯来源。'],search:['资料检索','围绕调研主题发现政策、文献与报告，逐步实现多来源检索、筛选与整理。'],graph:['知识图谱','探索政策、文献、机构与研究主题之间的联系，构建可追溯的交互式知识图谱。'],decision:['辅助决策','面向高校管理需求，提供政策对标、专题分析与调研报告辅助生成。'],recommend:['文献推荐','结合研究主题与知识积累，发现值得阅读的文献和相关资料。']};
function show(view){
 const home=view==='home', isChat=view==='chat', isSearch=view==='search',isFusion=view==='fusion',isGraph=view==='graph',isDecision=view==='decision',isRecommend=view==='recommend';
 document.body.classList.toggle('is-home',home);document.body.classList.toggle('is-recommend',isRecommend);
 document.querySelector('#workspace-intro h1').textContent=isSearch?'从一个问题，找到值得阅读的资料。':'让资料积累，成为研究的起点。';
 document.querySelector('#workspace-intro p').textContent=isSearch?'告诉我们你的研究需求，让检索、整理与知识积累顺畅衔接。':'连接你的本地知识与 DeepSeek，从一个问题开始深入探索。';
 $('fusion-view').hidden=!isFusion;if(isFusion&&typeof loadFusionReports==='function')loadFusionReports();$('home-view').hidden=!home;$('workspace-intro').hidden=home;$('workspace-heading').hidden=home;
 $('recommend-view').hidden=!isRecommend;if(isRecommend&&typeof openRecommendations==='function')openRecommendations();$('decision-view').hidden=!isDecision;if(isDecision&&typeof loadDecisionReports==='function')loadDecisionReports();$('knowledge-view').hidden=!isGraph;$('chat-view').hidden=!isChat;$('placeholder').hidden=home||isChat||isSearch||isFusion||isGraph||isDecision||isRecommend;$('research-view').hidden=!isSearch;$('new-chat').hidden=!isChat;
 if(isFusion){document.querySelector('#workspace-intro h1').textContent='让工作有全貌，让交接有依据。';document.querySelector('#workspace-intro p').textContent='从会议纪要到工作报告，把材料整理成可追问、可溯源的项目知识。'}
 if(isGraph){document.querySelector('#workspace-intro h1').textContent='让引用成为线索，让知识彼此连接。';document.querySelector('#workspace-intro p').textContent='导入本地材料，在可追溯的网络中探索文献、政策与资讯。'}
 if(isRecommend){document.querySelector('#workspace-intro h1').textContent='从已有积累，发现下一份值得读的资料。';document.querySelector('#workspace-intro p').textContent='结合资料库主题，持续发现近期研究、政策文件与新闻线索。'}
 if(isDecision){document.querySelector('#workspace-intro h1').textContent='从问题出发，形成有依据的工作建议。';document.querySelector('#workspace-intro p').textContent='明确目标与约束，比较可行路径，让每一项判断更便于讨论。'}
 $('view-title').textContent=isChat?'资料问答':home?'工作台首页':views[view][0];
 $('view-badge').textContent=(isChat||isSearch||isFusion||isGraph||isDecision||isRecommend)?'已开放':'开发中';
 for(const b of document.querySelectorAll('[data-view]')){b.classList.toggle('active',b.dataset.view===view);if(b.closest('#nav')){if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')}}
 if(!home&&!isChat){$('placeholder-title').textContent=views[view][0];$('placeholder-description').textContent=views[view][1]}
}
function renderModels(){
 const select=$('chat-model');select.replaceChildren();
 const values=[...new Set([currentModel,...availableModels].filter(Boolean))];
 for(const name of values){const o=document.createElement('option');o.value=name;o.textContent=name+(availableModels.length&&!availableModels.includes(name)?'（当前配置，未在列表中）':'');select.append(o)}
 select.value=currentModel;select.disabled=!configured||busy||modelsLoading||modelChanging;
 $('refresh-models').disabled=!configured||modelsLoading||busy||modelChanging;
 $('send').disabled=busy||modelChanging;
 if(!configured)$('model-status').textContent='请先配置 API Key';
}
async function loadModels(){
 const epoch=++modelEpoch, connectionVersion=connectionEpoch;connectionState('testing','正在测试连接…');modelsLoading=true;renderModels();$('model-status').textContent='正在获取模型…';
 try{const d=await api('test',{});if(epoch!==modelEpoch)return d;availableModels=d.models;if(connectionVersion===connectionEpoch)connectionState('success','连接成功 · 当前模型已响应');
 $('models').replaceChildren(...d.models.map(m=>{const o=document.createElement('option');o.value=m;return o}));
 $('model-status').textContent=d.models.length?'已获取 '+d.models.length+' 个可用模型':'未返回可用模型，可在设置中填写';return d;
 }catch(e){if(connectionVersion===connectionEpoch)connectionState('error','连接失败 · '+e.message);if(epoch===modelEpoch)$('model-status').textContent='获取失败，可点击刷新重试';throw e}
 finally{if(epoch===modelEpoch){modelsLoading=false;renderModels()}}
}
$('refresh-models').onclick=()=>loadModels().catch(e=>toast(e.message));
$('chat-model').onchange=async()=>{const selected=$('chat-model').value;modelChanging=true;renderModels();try{configView(await api('settings',{model:selected}));$('model-status').textContent='已切换至 '+selected;toast('后续消息将使用 '+selected)}catch(e){toast(e.message)}finally{modelChanging=false;renderModels()}};

document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>show(b.dataset.view));$('back-chat').onclick=()=>show('chat');
function openSettings(){$('settings-status').textContent='';$('settings-dialog').showModal()}
['open-settings','configure-library'].forEach(id=>$(id).onclick=openSettings);$('close-settings').onclick=()=>$('settings-dialog').close();
$('settings-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{configView(await api('settings',{api_endpoint:$('api-endpoint').value,bocha_api_key:$('bocha-key').value,api_key:$('api-key').value,model:$('model').value,directory:$('directory').value,policy_directory:$('policy-directory').value}));$('api-key').value='';$('bocha-key').value='';libraryView((await api('state')).library);availableModels=[];renderModels();$('settings-status').textContent='设置已保存，正在测试连接…';try{const d=await loadModels();$('settings-status').textContent=d.message}catch(e){$('settings-status').textContent='设置已保存。'+e.message}}catch(e){$('settings-status').textContent=e.message}finally{button.disabled=false}};
$('test').onclick=async()=>{$('test').disabled=true;$('settings-status').textContent='正在测试已保存网关和模型…';try{const d=await loadModels();$('settings-status').textContent=d.message+'\n可用模型：'+d.models.join('、')}catch(e){$('settings-status').textContent=e.message}finally{$('test').disabled=false}};
$('clear-key').onclick=async()=>{try{configView(await api('settings',{clear_key:true}));modelEpoch++;modelsLoading=false;availableModels=[];renderModels();$('api-key').value='';$('settings-status').textContent='本机保存的密钥已删除。'}catch(e){$('settings-status').textContent=e.message}};
$('scan').onclick=async()=>{$('scan').disabled=true;$('scan').textContent='读取中…';try{const d=await api('scan',{});libraryView(d);toast('资料库已更新：'+d.files.length+' 份可用资料')}catch(e){toast(e.message)}finally{$('scan').disabled=false;$('scan').textContent='↻ 更新'}};
document.querySelectorAll('.suggestions button').forEach(b=>b.onclick=()=>{$('question').value=b.textContent;$('question').focus()});
function message(role,text){const el=document.createElement('div');el.className='message '+role;const label=document.createElement('div');label.className='speaker';label.textContent=role==='user'?'你':'浙智研析 · DeepSeek';const content=document.createElement('div');content.textContent=text;el.append(label,content);$('messages').append(el);$('messages').scrollTop=$('messages').scrollHeight;return {el,content}}
$('new-chat').onclick=()=>{if(busy)return;history=[];$('messages').replaceChildren();message('assistant','新的研究对话已开始。你想了解什么？')};
$('question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit()}};
$('chat-form').onsubmit=async e=>{e.preventDefault();const question=$('question').value.trim();if(!question||busy||modelChanging)return;if(!configured){openSettings();toast('请先保存 DeepSeek API Key');return}busy=true;renderModels();$('send').disabled=true;$('new-chat').disabled=true;$('send').textContent='正在思考…';document.querySelector('.welcome')?.remove();message('user',question);$('question').value='';const out=message('assistant','正在整理资料并等待回答…');try{const data=await api('chat',{question,history,use_library:$('use-library').checked});out.content.textContent=data.answer;history.push({role:'user',content:question},{role:'assistant',content:data.answer});history=history.slice(-12);if(data.sources.length){const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='本次提供给模型的资料片段 · '+data.sources.length+' 条';details.append(summary);for(const s of data.sources){const section=document.createElement('details');const title=document.createElement('summary');title.textContent='['+s.id+'] '+s.path+' · 字符位置 '+s.offset;const text=document.createElement('div');text.className='source-text';text.textContent=s.text;section.append(title,text);details.append(section)}out.el.append(details)}const usage=document.createElement('div');usage.className='usage';usage.textContent=(data.sources.length?'已提供资料片段':'本次未提供资料正文')+(data.usage.total_tokens?' · '+data.usage.total_tokens+' tokens':'');out.el.append(usage)}catch(e){out.content.textContent=e.message;out.el.classList.add('error');$('question').value=question}finally{busy=false;renderModels();$('send').disabled=false;$('new-chat').disabled=false;$('send').textContent='发送问题 ↗';$('messages').scrollTop=$('messages').scrollHeight}};
api('state').then(s=>{configView(s.settings);libraryView(s.library);if(configured)loadModels().catch(e=>toast(e.message))}).catch(e=>toast(e.message));

document.querySelector('.brand').onclick=e=>{e.preventDefault();show('home')};
show("home");

$('clear-bocha').onclick=async()=>{try{configView(await api('settings',{clear_bocha_key:true}));$('bocha-key').value='';toast('已删除博查密钥')}catch(e){toast(e.message)}};

$('api-provider').onchange=()=>{const value=$('api-provider').value;if(value==='official'){$('api-endpoint').value='https://api.deepseek.com/chat/completions';$('model').value='deepseek-flash'}if(value==='zju'){$('api-endpoint').value='https://modelgateway.zju.edu.cn/v1/chat/completions';$('model').value='deepseek-v4-flash-780k-local'}markApiDirty()};
function markApiDirty(){$('test').disabled=true;connectionEpoch++;connectionState('unknown','配置已修改 · 请先保存再测试')}
for(const id of ['api-endpoint','api-key','model'])$(id).addEventListener('input',markApiDirty);

$('bocha-key').addEventListener('input',()=>{bochaEpoch++;bochaState('unknown','密钥已修改 · 请保存并测试')});
$('test-bocha').onclick=async()=>{
 const epoch=++bochaEpoch,button=$('test-bocha'),key=$('bocha-key').value.trim();button.disabled=true;bochaState('testing','正在测试博查搜索…');
 try{
  if(key){await api('settings',{bocha_api_key:key});if(epoch!==bochaEpoch)return;$('bocha-key').value='';}
  const result=await api('bocha/test',{});if(epoch===bochaEpoch)bochaState('success',result.message);
 }catch(e){if(epoch===bochaEpoch)bochaState('error',e.message)}finally{button.disabled=false}
};
