"""Complete pagination or explicit failure. Source watermarks are not changed here."""
from common import *
from metadata import *
from datetime import timedelta
def pm_search(client,query):
 out=[];total=None;start=0
 while total is None or start<total:
  d=client.get(NCBI+'esearch.fcgi',{'db':'pubmed','term':query,'retmode':'json','retmax':2000,'retstart':start},ttl=3600)['esearchresult']
  if d.get('errorlist') or d.get('ERROR'):raise ValueError('PubMed query errors: '+str(d))
  n=int(d['count'])
  if n>=10000:raise ValueError('PubMed >=10000; requires date-partitioned search before publication; no truncated success')
  if total is not None and n!=total:raise ValueError('PubMed count changed during pagination; retry required')
  total=n;ids=d['idlist']
  if not ids and start<total:raise ValueError('Empty PubMed page before end')
  out+=ids;start+=len(ids)
 if len(set(out))!=total:raise ValueError('PubMed unique count mismatch')
 return out,total
def ep_search(client,query):
 result={};cursor='*';total=None;seen=set()
 while True:
  d=client.get(EPMC+'search',{'query':query,'format':'json','resultType':'core','pageSize':1000,'cursorMark':cursor},ttl=3600);n=int(d['hitCount'])
  if total is not None and n!=total:raise ValueError('EPMC count changed during pagination')
  total=n;page=d.get('resultList',{}).get('result',[])
  for x in page:result[x['source']+':'+x['id']]=x
  if len(result)==total:break
  nxt=d.get('nextCursorMark')
  if not page or not nxt or nxt==cursor or nxt in seen:raise ValueError('EPMC cursor incomplete')
  seen.add(cursor);cursor=nxt
 if len(result)!=total:raise ValueError('EPMC unique count mismatch')
 return result,total
def searches(client,cfg,mode,previous):
 stamp=now();date=datetime.fromisoformat(stamp);until=date.date().isoformat();logs=[];unions={'pubmed':set(),'europepmc':{}};source_ok={}
 for src in ['pubmed','europepmc']:
  source_ok[src]=True
  anchor=date;water=previous.get('source_watermarks',{}).get(src,{}).get('through')
  if water:anchor=min(date,datetime.fromisoformat(water))
  since=(anchor-timedelta(days=cfg['lookback_days'])).date().isoformat()
  try:
   if src=='europepmc':
    fields=client.get(EPMC+'fields',{'format':'json'},ttl=86400*30)
    advertised={x['term'] for x in fields['searchTermList']['searchTerms']}
    if not {'FIRST_PDATE','FIRST_IDATE','UPDATE_DATE'}.issubset(advertised):raise ValueError('EPMC date fields changed')
   else:
    fields=client.get(NCBI+'einfo.fcgi',{'db':'pubmed','retmode':'json'},ttl=86400*30)['einforesult']['dbinfo'][0]['fieldlist']
    if not {'PDAT','EDAT','MDAT','CRDT'}.issubset({f['name'] for f in fields}):raise ValueError('PubMed date fields changed')
  except Exception as e:
   source_ok[src]=False;logs.append({'source':src,'branch':'field_validation','status':'failed','error':str(e),'pagination_complete':False});continue
  for q in cfg['queries']:
   query=q[src]
   if mode!='history':
    if src=='pubmed':query+=' AND ('+' OR '.join(f'("{since.replace("-","/")}"[{f}] : "{until.replace("-","/")}"[{f}])' for f in ['PDAT','EDAT','MDAT','CRDT'])+')'
    else:query+=' AND ('+' OR '.join(f'{f}:[{since} TO {until}]' for f in ['FIRST_PDATE','FIRST_IDATE','UPDATE_DATE'])+')'
   rec={'source':src,'branch':q['id'],'query':query,'from':None if mode=='history' else since,'to':until,'started_at':now()}
   try:
    found,total=pm_search(client,query) if src=='pubmed' else ep_search(client,query)
    unions[src].update(found);rec.update(status='success',hits=total,fetched=len(found),pagination_complete=True)
   except Exception as e:source_ok[src]=False;rec.update(status='failed',error=str(e),pagination_complete=False)
   logs.append(rec);print(src,q['id'],rec['status'],rec.get('hits'),flush=True)
 return unions,logs,source_ok
def initial():
 cfg=read(ROOT/'config/search.json');client=Client();u,logs,ok=searches(client,cfg,'history',{})
 atomic(ROOT/'data/sources/discovery_pubmed_ids.json',sorted(u['pubmed']));atomic(ROOT/'data/sources/discovery_epmc.json',u['europepmc']);atomic(ROOT/'data/reports/baseline_search.json',{'mode':'history','started_at':logs[0]['started_at'],'finished_at':now(),'sources':ok,'queries':logs,'pubmed_unique':len(u['pubmed']),'epmc_unique':len(u['europepmc']),'overlap_med':len(u['pubmed']&{x['id'] for x in u['europepmc'].values() if x['source']=='MED'}),'complete':all(ok.values()),'source_dependence':'PubMed和Europe PMC共享MEDLINE来源，不能视为完全独立覆盖'})
 if u['pubmed']:
  report=read(ROOT/'data/reports/baseline_search.json');report['search_complete']=report.pop('complete');report['complete']=False;report['metadata_complete']=False;atomic(ROOT/'data/reports/baseline_search.json',report)
  try:
   m=fetch_pm(client,sorted(u['pubmed']));atomic(ROOT/'data/sources/discovery_pubmed.json',m);report['metadata_complete']=True;report['complete']=report['search_complete']
  except Exception as e:report['metadata_error']=str(e)
  report['finished_at']=now();atomic(ROOT/'data/reports/baseline_search.json',report)
 print('baseline saved',ok,flush=True)
if __name__=='__main__':initial()
