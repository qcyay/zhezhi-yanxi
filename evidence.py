"""Public article extraction and deterministic relevance gates; no remote HTML rendering."""
import datetime as dt
import io
import ipaddress
import re
import queue
import threading
import policies
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser

FAKE_RANGES=(ipaddress.ip_network('198.18.0.0/15'),ipaddress.ip_network('fdfe:dcba:9876::/48'))

def fake_dns_address(value):
    address=ipaddress.ip_address(value)
    return any(address in network for network in FAKE_RANGES if address.version==network.version)

def fake_dns_enabled():
    # Some local VPNs resolve public names to a synthetic address pool. Only
    # recognize the known pools when a fixed public control hostname does too.
    try:
        addresses=socket.getaddrinfo('www.bing.com',443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(fake_dns_address(a[4][0]) for a in addresses)
    except OSError:return False

def public_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,80,443):
        raise ValueError('仅允许公开 HTTP/HTTPS 网页')
    try:literal=ipaddress.ip_address(parsed.hostname)
    except ValueError:literal=None
    if literal and not literal.is_global:raise ValueError('不允许私有或保留 IP 地址')
    if '.' not in parsed.hostname or parsed.hostname.endswith(('.local','.internal','.localhost')):raise ValueError('不允许本地网络主机')
    addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
    fake=not literal and fake_dns_enabled()
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global and not (fake and fake_dns_address(a[4][0])) for a in addresses):
        raise ValueError('不允许访问本地或私有网络地址')
    return url

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class Element:
    def __init__(self,tag='',attrs=None):
        self.tag=tag;self.attrs=dict(attrs or []);self.children=[]
    def text(self):
        if self.tag in ('script','style','nav','footer','header','noscript','form','svg','button'):
            return ''
        text=''.join(c.text() if isinstance(c,Element) else c for c in self.children)
        return '\n'+text+'\n' if self.tag in ('p','div','section','article','li','h1','h2','h3','br','tr') else text
    def descendants(self):
        yield self
        for child in self.children:
            if isinstance(child,Element):yield from child.descendants()

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.root=Element('root');self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        e=Element(tag,attrs);self.stack[-1].children.append(e)
        if tag not in ('meta','link','img','br','hr','input','source','wbr','area','base','embed','param'):
            self.stack.append(e)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if self.stack[-1].tag==tag:self.stack.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                del self.stack[i:];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def normalize(text):
    return '\n'.join(line for line in (re.sub(r'[\t \xa0\u3000]+',' ',s).strip() for s in text.splitlines()) if line)

def extract_html(raw,charset=''):
    declared=re.search(br'charset\s*=\s*["\x27]?([\w-]+)',raw[:12000],re.I)
    choices=[declared.group(1).decode() if declared else '',charset,'utf-8','gb18030']
    for encoding in choices:
        try:
            if not encoding:continue
            html=raw.decode(encoding);break
        except (UnicodeError,LookupError):pass
    else:html=raw.decode('utf-8',errors='replace')
    doc=Document();doc.feed(html)
    nodes=list(doc.root.descendants());meta={}
    for n in nodes:
        if n.tag=='meta':meta[(n.attrs.get('name') or n.attrs.get('property') or '').lower()]=n.attrs.get('content','')
    title=meta.get('articletitle') or meta.get('og:title') or next((normalize(n.text()) for n in nodes if n.tag=='h1'),'') or next((normalize(n.text()) for n in nodes if n.tag=='title'),'')
    def score(n):
        text=normalize(n.text());length=len(text)
        links=sum(len(normalize(x.text())) for x in n.descendants() if x.tag=='a')
        ratio=links/max(length,1)
        descriptor=(n.attrs.get('class','')+' '+n.attrs.get('id','')).lower()
        bonus=10000 if re.search(r'trs_editor|article[-_]?body|article[-_]?content|zoom|pages_content|detail[-_]?content|rich_media_content',descriptor) else 2000 if n.tag=='article' else 0
        paragraphs=sum(1 for x in n.descendants() if x.tag=='p' and len(normalize(x.text()))>40)
        return min(length,18000)*(1-ratio*1.8)+paragraphs*100+bonus if length>100 else -1
    candidates=[n for n in nodes if n.tag in ('article','main','section','div','body')]
    best=max(candidates,key=score) if candidates else doc.root
    text=normalize(best.text())
    linked=sum(len(normalize(x.text())) for x in best.descendants() if x.tag=='a')/max(len(text),1)
    date=next((meta[k] for k in ('article:published_time','pubdate','publishdate','publishtime','date','pubtime','articlepublishtime','dc.date.issued') if meta.get(k)),'')
    if not date:date=next((n.attrs.get('datetime','') for n in nodes if n.tag=='time' and n.attrs.get('datetime')),'')
    if not date:
        match=re.search(r'(?:发布时间|发布日期|时间|日期)\s*[:：]?\s*(20\d{2}[年/.-]\d{1,2}[月/.-]\d{1,2})',normalize(doc.root.text())[:16000])
        date=match.group(1) if match else ''
    match=re.search(r'(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})',date)
    date='-'.join([match[1],match[2].zfill(2),match[3].zfill(2)]) if match else ''
    return {'title':title[:500],'text':text,'date':date,'link_density':linked,'truncated':False}

def _read_article(url):
    public_url(url)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 ZheZhiYanXi/0.4','Accept':'text/html,application/pdf;q=0.9'})
    with urllib.request.build_opener(Redirect()).open(req,timeout=18) as response:
        public_url(response.url)
        raw=response.read(15_000_001)
        if len(raw)>15_000_000:raise ValueError('网页或 PDF 超过 15 MB')
        mime=response.headers.get_content_type();charset=response.headers.get_content_charset() or '';final=response.url
    if raw.startswith(b'%PDF'):
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw))
        if len(reader.pages)>300:raise ValueError('PDF 超过300页，请阅读原件')
        pages=[policies.normalize(p.extract_text() or '') for p in reader.pages]
        if sum(len(p.strip()) for p in pages)<160:raise ValueError('扫描 PDF 无可提取文字')
        text='\n\n'.join(f'第 {i+1} 页\n'+p for i,p in enumerate(pages))
        out={'title':str(reader.metadata.title or '') if reader.metadata else '', 'text':text,'date':'','link_density':0,'truncated':False,'is_pdf':True}
    elif mime in ('text/html','application/xhtml+xml','text/plain'):
        out=extract_html(raw,charset)
    else:raise ValueError('不支持的网页内容类型')
    if len(out['text'])<160:raise ValueError('网页正文不足，可能需要登录或动态加载')
    out.update(url=final,content_status='已提取正文',fetched_at=dt.datetime.now().isoformat(timespec='seconds'))
    return out

def read_article(url):
    result=queue.Queue(maxsize=1)
    def work():
        try:result.put((True,_read_article(url)))
        except Exception as e:result.put((False,e))
    threading.Thread(target=work,daemon=True).start()
    try:ok,value=result.get(timeout=25)
    except queue.Empty:raise TimeoutError('正文读取超过 25 秒')
    if not ok:raise value
    return value

def landing_page(url,title):
    path=urllib.parse.urlsplit(url).path.lower().rstrip('/')
    return bool(re.search(r'/(?:index|node_\d+)\.s?html?$',path)) or bool(re.match(r'^(?:主页|首页)\s*[>＞]',title)) or path in ('','/en','/english','/cn','/index.html','/index.htm','/en/index.html','/qggxmd') or bool(re.search(r'^(?:首页|网站首页|全国普通高等学校名单|清华大学|tsinghua university)(?:\s*[-|—].*)?$',title.strip(),re.I))

def terms(plan,brief):
    zh=plan.get('core_terms',[]);en=plan.get('english_terms',[])
    values=[]
    if 2<=len(brief['topic'])<=16:values.append(brief['topic'])
    for word in zh if isinstance(zh,list) else []:
        if isinstance(word,str) and 2<=len(word)<=30 and word in brief['topic']:values.append(word)
    for word in en if isinstance(en,list) else []:
        if isinstance(word,str) and 3<=len(word)<=60:values.append(word)
    values.extend(policies.expanded_terms(brief['topic']))
    stop={'高校','大学','研究','政策','文件','新闻','教育','higher education','university','universities','research','policy','news'}
    return list(dict.fromkeys(w.lower().strip() for w in values if w.lower().strip() not in stop))[:12]

def matched_terms(text,words):
    text=text.lower()
    return [w for w in words if (re.search(r'(?<![a-z])'+re.escape(w)+r'(?![a-z])',text) if re.search('[a-z]',w) else w in text)]

def verify(item,plan,brief):
    item=dict(item);words=terms(plan,brief)
    if item['type']=='policy':words=list(dict.fromkeys(words+policies.expanded_terms(brief['topic'])))
    local=bool(item.get('local_path'))
    if item['type']!='papers':
        if not local and landing_page(item['url'],item['title']):return None,'首页或目录页'
        try:
            article={'title':item['title'],'text':item['content'],'date':item['date'],'link_density':0,'url':item['url'],'truncated':False,'fetched_at':'本地文件','content_status':item['content_status']} if local else read_article(item['url'])
        except Exception:return None,'正文无法读取'
        if not local and (landing_page(article['url'],article['title']) or article['link_density']>.35):return None,'首页或导航列表'
        if len(article['text'])<240 and not item.get('scanned'):return None,'文章内容不足'
        item.update(content=article['text'],content_status=article['content_status'],truncated=article['truncated'],fetched_at=article['fetched_at'],url=article['url'])
        item['title']=article['title'] or item['title'];item['date']=article['date'] or item['date']
        if not item['date']:
            dated=re.search(r'(?:/|t)(20\d{2})(\d{2})(\d{2})(?:_|/|\.)',item['url'])
            if dated:
                try:item['date']=dt.date(int(dated[1]),int(dated[2]),int(dated[3])).isoformat()
                except ValueError:pass
        if item['type']=='policy' and not local and not re.search(r'意见|通知|办法|条例|规定|方案|指南|规划|细则|决定|标准|指引|法|policy|guideline|regulation|act\b',item['title'],re.I):return None,'不符合政策文件类型'
        if item['type']=='news' and not item['date']:return None,'无法确认新闻发布日期'
        if item['type']=='news' and not re.search(r'记者|报道|通讯员|消息|获悉|召开|举行|宣布|启动|揭牌|reported|announced|launch|said|according|news|案例|实践|经验|转型|访谈|观点|解读|研究发现',item['title']+'\n'+item['content'][:4000],re.I):return None,'缺少具体新闻报道特征'
    else:
        item.update(content=item.get('excerpt',''),content_status='数据库摘要（非全文）',truncated=False)
    if brief['period']!='all' and item.get('date'):
        match=re.search(r'20\d{2}',item['date'])
        if match and not dt.date.today().year-int(brief['period'])+1<=int(match[0])<=dt.date.today().year:
            if item['type']=='policy' and brief.get('include_older_policies',True) and int(match[0])<dt.date.today().year:item['date_note']='较早基础制度，效力与版本请核验'
            else:return None,'不在所选时间范围'
    evidence=item['title']+'\n'+item.get('content','')
    matches=matched_terms(evidence,words)
    if not matches:return None,'核心主题无命中'
    title_matches=matched_terms(item['title'],words)
    body_matches=matched_terms(item.get('content',''),words)
    if item['type']!='papers' and not body_matches and not item.get('scanned'):return None,'正文未命中主题'
    score=min(94,58+(16 if title_matches else 0)+(12 if body_matches else 0)+min(8,len(matches)*2))
    item.update(keywords=matches[:6],lexical_score=score,relevance=score,score_method='正文与标题规则评分' if item['type']!='papers' else '标题与摘要规则评分',score_reason='核心词命中：'+ '、'.join(matches[:6]))
    paragraphs=item.get('content','').splitlines()
    snippets=[p for p in paragraphs if matched_terms(p,words)]
    item['evidence_excerpt']='\n'.join(p[:700] for p in snippets[:5])[:2800] or item['title']
    if item.get('scanned'):item.update(score_method='仅标题匹配（扫描件正文未识别）',score_reason='仅从标题判断相关性，请打开 PDF 原件核验。')
    if item['type']!='papers':item['excerpt']=item['evidence_excerpt'][:1800]
    return item,''
