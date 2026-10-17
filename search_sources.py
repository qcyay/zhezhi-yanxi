"""Optional Bocha search adapter. Credentials are supplied by the host at call time."""
import json,urllib.request
KEY_PROVIDER=lambda:''
def configured():return bool(KEY_PROVIDER())
def search(query,freshness='noLimit'):
 key=KEY_PROVIDER()
 if not key:return []
 request=urllib.request.Request('https://api.bochaai.com/v1/web-search',data=json.dumps({'query':query,'freshness':freshness,'summary':True,'count':30}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=20) as response:data=json.loads(response.read(3000000))
 except Exception:raise ValueError('博查搜索连接失败，请检查独立密钥、额度或网络。')
 payload=data.get('data',data)
 if not isinstance(payload,dict) or ('code' in data and data['code'] not in (200,'200',0,'0')):raise ValueError('博查搜索未返回可用结果，请检查配置。')
 return [{'title':r.get('name',''),'url':r.get('url',''),'excerpt':r.get('snippet') or r.get('summary',''),'source':'博查搜索 API','date':r.get('datePublished','')[:10]} for r in payload.get('webPages',{}).get('value',[])]
