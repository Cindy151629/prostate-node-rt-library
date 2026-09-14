"""Verify body + identity; HTTP success alone never means verified full text."""
import xml.etree.ElementTree as ET,concurrent.futures,difflib
from common import *
from metadata import EPMC,text
def identify_html(raw,p):
 s=clean(raw);lo=s.lower()
 blocked=any(x in lo[:1500] for x in ['verify you are human','checking your browser','access denied','captcha','just a moment','log in to access','sign in to access','login required'])
 identifiers=bool(p.get('doi') and doi(p['doi']) in raw.lower()) or bool(p.get('pmid') and p['pmid'] in raw)
 return {'status':'access_restricted' if blocked else 'publisher_page_unconfirmed','body_confirmed':False,'identity_hint':identifiers,'page_chars':len(s),'reason':'登录／验证／拦截页' if blocked else '已取得页面；尚未确认其为对应正文，不以HTTP200当作全文'}
def verify_jats(raw,p):
 root=ET.fromstring(raw);ids={e.get('pub-id-type'):''.join(e.itertext()).strip() for e in root.findall('.//article-meta/article-id')};body=root.find('.//body');n=len(''.join(body.itertext())) if body is not None else 0
 match=(p.get('pmid') and ids.get('pmid')==p['pmid']) or (p.get('doi') and doi(ids.get('doi'))==doi(p['doi']))
 if not match:return {'status':'identity_conflict','body_confirmed':False,'found_ids':ids,'reason':'正文ID与目标文献不匹配'}
 if n<500:return {'status':'no_confirmed_body','body_confirmed':False,'found_ids':ids,'reason':'没有足够正文；不将摘要/简短记录当完整研究正文'}
 return {'status':'body_obtained','body_confirmed':True,'found_ids':ids,'body_chars':n,'body_text':clean(' '.join(body.itertext())),'article_title':text(root,'.//article-title'),'version':'PMC归档全文；出版社版/作者稿需结合归档信息逐条判断'}
def verify_one(client,p,ep,force=False):
 pmcid=ep.get('pmcid') or p.get('pmcid');attempts=[];rec={'id':p['id'],'seed_id':p.get('seed_id'),'checked_at':now(),'body_confirmed':False,'pmcid':pmcid or ''}
 if pmcid:
  url=EPMC+pmcid+'/fullTextXML'
  try:
   raw=client.get(url,fmt='text');v=verify_jats(raw,p);attempts.append({'url':url,'status':v['status']})
   if v['body_confirmed']:
    body=v.pop('body_text');dest=ROOT/'data/sources/fulltext';dest.mkdir(exist_ok=True);atomic(dest/(p['id']+'.xml'),raw);atomic(dest/(p['id']+'.txt'),body);return {**rec,**v,'url':url,'attempts':attempts,'body_sha256':hashlib.sha256(body.encode()).hexdigest()}
  except Exception as e:attempts.append({'url':url,'status':'access_failed','error':str(e)})
 # Publisher pages are retained as evidence but never auto-upgraded to full text.
 url='https://doi.org/'+p['doi']
 try:
  raw=client.get(url,fmt='text');v=identify_html(raw,p);dest=ROOT/'data/sources/publisher';dest.mkdir(exist_ok=True);atomic(dest/(p['id']+'.html'),raw);rec.update(v,url=url)
 except Exception as e:rec.update(status='access_restricted',reason=str(e),url=url)
 rec['attempts']=attempts+[{'url':url,'status':rec['status']}]
 if pmcid:rec['indexed_fulltext_url']='https://pmc.ncbi.nlm.nih.gov/articles/'+pmcid+'/'
 rec['index_open_access']=ep.get('isOpenAccess')=='Y';return rec
def run():
 seeds=read(ROOT/'data/seeds.json');ep=read(ROOT/'data/sources/epmc.json',{});existing=read(ROOT/'data/sources/fulltext_checks.json',{});client=Client()
 todo=[p for p in seeds if p['id'] not in existing]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  jobs={ex.submit(verify_one,client,p,ep.get(p['pmid'],{})):p for p in todo}
  for f in concurrent.futures.as_completed(jobs):
   p=jobs[f]
   try:existing[p['id']]=f.result()
   except Exception as e:existing[p['id']]={'id':p['id'],'status':'error','body_confirmed':False,'reason':str(e),'checked_at':now()}
   atomic(ROOT/'data/sources/fulltext_checks.json',existing)
   if len(existing)%15==0:print('checked',len(existing),'bodies',sum(x['body_confirmed'] for x in existing.values()),flush=True)
 atomic(ROOT/'data/reports/fulltext_network.json',client.events);print('finished',len(existing),flush=True)
if __name__=='__main__':run()
