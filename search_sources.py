"""Optional Bocha search adapter. Credentials are supplied by the host at call time."""
import json,urllib.request,urllib.error
KEY_PROVIDER=lambda:''
def configured():return bool(KEY_PROVIDER())
def search(query,freshness='noLimit',count=30):
 key=KEY_PROVIDER()
 if not key:return []
 request=urllib.request.Request('https://api.bochaai.com/v1/web-search',data=json.dumps({'query':query,'freshness':freshness,'summary':True,'count':count}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=20) as response:data=json.loads(response.read(3000000))
 except urllib.error.HTTPError as e:
  raise ValueError({401:'博查认证失败（401），请检查博查密钥。',403:'博查拒绝访问（403），请检查接口权限。',402:'博查可用额度不足（402），请检查资源包或余额。',429:'博查请求受限（429），请稍后重试并检查额度。'}.get(e.code,f'博查服务返回 HTTP {e.code}，请稍后重试。')) from None
 except (urllib.error.URLError,TimeoutError):raise ValueError('博查网络连接失败或超时，请检查网络后重试。') from None
 except (ValueError,TypeError):raise ValueError('博查返回内容格式异常，请稍后重试。') from None
 if not isinstance(data,dict):raise ValueError('博查返回内容格式异常。')
 payload=data.get('data',data)
 if not isinstance(payload,dict) or ('code' in data and data['code'] not in (200,'200',0,'0')):raise ValueError('博查搜索未返回可用结果，请检查配置。')
 return [{'title':r.get('name',''),'url':r.get('url',''),'excerpt':r.get('snippet') or r.get('summary',''),'source':'博查搜索 API','date':r.get('datePublished','')[:10]} for r in payload.get('webPages',{}).get('value',[])]


def test_connection():
 if not configured():raise ValueError('请先保存博查 API Key。')
 results=search('浙江大学 数据治理',count=1)
 return {'connected':True,'count':len(results),'message':f'博查连接成功 · 实际搜索返回 {len(results)} 条记录'}
