"""Transparent ranking hints: database citations or verified source category."""
import math,urllib.parse

def metric(item):
 count=item.get('citation_count')
 if item['type']=='papers':
  known=isinstance(count,int) and not isinstance(count,bool) and count>=0
  return {'score':max(1,min(100,round(math.log10(1+count)*25))) if known else None,'label':(('暂未记录引用' if count==0 else '被引 '+str(count)+' 次')) if known else '被引数未知','basis':(item.get('citation_source') or item.get('source','数据库'))+'；按 log10(1+被引数) × 25 转换为排序分，最低1，上限100；不代表论文质量。','kind':'citations','count':count if known else None}
 host=(urllib.parse.urlsplit(item.get('url','')).hostname or '').lower()
 if host=='gov.cn' or host.endswith('.gov.cn'):score,label=85,'政府官方来源'
 elif host.endswith('.edu.cn'):score,label=75,'高校官方来源'
 elif any(host==d or host.endswith('.'+d) for d in ('xinhuanet.com','news.cn','people.com.cn','cctv.com')):score,label=70,'中央新闻机构来源'
 else:score,label=None,'来源权威性待核验'
 return {'score':score,'label':label,'basis':'按原始链接所属机构类别提供排序参考；不推断发布级别、政策效力或内容真实性。跨类型分数不代表可直接比较的实际影响力。','kind':'authority','count':None}
