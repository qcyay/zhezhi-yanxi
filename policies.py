"""Read-only local policy corpus and domain-specific query expansion."""
import hashlib
import re
import unicodedata
import urllib.parse
from functools import lru_cache
from pathlib import Path

DEFAULT_DIRECTORY=''
DATA_GOVERNANCE=['数据治理','数据管理','数据安全','数据共享','公共数据','政务数据','科学数据','教育数据','数据分类','数据标准','个人信息保护','网络安全','教育数字化','管理信息化','基础数据']

def expanded_terms(topic):
    return DATA_GOVERNANCE if '数据治理' in topic else []

def normalize(text):
    text=unicodedata.normalize('NFKC',text).translate(str.maketrans({'⺠':'民','⻓':'长','⻔':'门','⻅':'见','⻔':'门','⻢':'马','⻚':'页','⻛':'风','⻋':'车'}))
    return re.sub(r'(?<=[\u4e00-\u9fff]) +(?=[\u4e00-\u9fff])','',text)

def level(title,text=''):
    if re.search(r'大学|学院',title):return '高校'
    if re.search(r'省|市|自治区',title):return '省市'
    if re.search(r'教育部|教育数据|教育基础|教育系统',title):return '教育部'
    if re.search(r'中华人民共和国|国务院|科学数据',title):return '国家'
    return '其他部委'

@lru_cache(maxsize=150)
def read_pdf(path,modified,size):
    from pypdf import PdfReader
    reader=PdfReader(path)
    if len(reader.pages)>300 or size>25_000_000:raise ValueError('政策 PDF 超过 300 页或 25 MB')
    pages=[normalize(page.extract_text() or '') for page in reader.pages]
    text='\n\n'.join(f'〔第 {i+1} 页〕\n{t}' for i,t in enumerate(pages))
    # PDF browser print footers and the government's correction link encode
    # the original page. Prefer those over navigation annotations.
    urls=[]
    for page in reader.pages:
        for ref in page.get('/Annots',[]):
            uri=str(ref.get_object().get('/A',{}).get('/URI',''))
            if 'zfwzgl.www.gov.cn' in uri:
                original=urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query).get('url',[''])[0]
                if original:urls.append(original)
    if not urls:
        urls=re.findall(r'https?://[^\s<>]+',text)
    origin=next((u.rstrip('.,，。)）') for u in urls if re.search(r'gov\.cn|edu\.cn',u) and re.search(r'\.(?:html?|pdf)(?:\?|$)',u) and not re.search(r'/index\.|/home/',u)), '')
    match=re.search(r'(20\d{2})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})',normalize('\n'.join(pages[:2])))
    date=f'{match[1]}-{int(match[2]):02}-{int(match[3]):02}' if match else ''
    return {'content':text,'date':date,'origin_url':origin,'page_count':len(pages),'scanned':sum(len(p.strip()) for p in pages)<160}

def records(directory=DEFAULT_DIRECTORY):
    if not directory:return [],['未配置本地政策目录，仅检索公开来源。']
    root=Path(directory).expanduser()
    if not root.is_dir():return [],['本地政策目录不存在，可在设置中修改。']
    result=[];issues=[]
    for path in sorted(root.rglob('*.pdf'))[:150]:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):continue
        try:
            stat=path.stat();data=read_pdf(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
            identity='P'+hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
            title=path.stem.split('_')[0]
            result.append(dict(data,id=identity,local_id=identity,local_path=str(path.resolve()),title=title,type='policy',source='本地政策库',publisher=level(title),policy_level=level(title),url=data['origin_url'],doi='',authors='',excerpt='',query='本地政策全文检索',truncated=False,content_status='扫描 PDF（请查看原件）' if data['scanned'] else '本地 PDF 全文'))
        except Exception as e:issues.append(path.name+'：'+str(e))
    return result,issues

def candidates(brief,directory):
    items,issues=records(directory)
    if not brief.get('use_local_policies',True):return [],[]
    words=expanded_terms(brief['topic']) or [brief['topic']]
    scopes=brief.get('policy_levels',['国家','教育部','其他部委','省市','高校'])
    return [i for i in items if i['policy_level'] in scopes and any(w in (i['title']+i['content']) for w in words)],issues

def scoped_queries(plan,brief):
    # A separate query for each authority tier avoids a single university-
    # centred query accidentally suppressing national and ministry policies.
    words=expanded_terms(brief['topic']) or [brief['topic']]
    domains={'国家':'site:gov.cn','教育部':'site:moe.gov.cn','其他部委':'(site:ndrc.gov.cn OR site:cac.gov.cn OR site:most.gov.cn)','省市':'site:gov.cn 省 市','高校':'site:edu.cn'}
    queries=[]
    for i,scope in enumerate(brief.get('policy_levels',list(domains))):
        word=words[i%len(words)]
        queries.append(f'"{word}" (办法 OR 条例 OR 意见 OR 标准) {domains[scope]}')
    for domain in ('nda.gov.cn','miit.gov.cn','moe.gov.cn','ndrc.gov.cn','zj.gov.cn','edu.cn'):
        queries.append(f'"{words[0]}" 通知 办法 site:{domain}')
    return list(dict.fromkeys(queries))
