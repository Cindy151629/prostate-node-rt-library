"""Ordinary Python updater; safe candidate snapshot, persistent registry, no generated conclusions."""
import argparse,copy,traceback,collections
from common import *
from metadata import *
from discovery import searches
from library import *
from fulltext import verify_one
from versions import refresh as refresh_versions
VOLATILE={'checked_at','verified_at','retrieved_at','reviewed_at'}
def stable(v):
 if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k not in VOLATILE}
 if isinstance(v,list):return [stable(x) for x in v]
 return v
def diff_records(old,new):
 a={r['id']:r for r in old};b={r['id']:r for r in new}
 return {'added':[k for k in b if k not in a],'updated':[k for k in b if k in a and digest(stable(b[k]))!=digest(stable(a[k]))],'removed':[k for k in a if k not in b]}
def coverage(lib):
 directions={'疗效/失败模式':'生存|失败|复发|PFS|控制','照射范围/剂量':'剂量|Gy|CTV|靶区|覆盖|扩大|加量','毒性/生活质量':'毒性|生活质量|QoL','系统联合':'ADT|激素|阿比特龙|Lu-PSMA','随机比较':'随机'}
 rows=[]
 for k,label in SECTIONS.items():
  rec=[x for x in lib if x['section']==k];row={'section':k,'name':label,'papers':len(rec),'directions':{}}
  for d,pat in directions.items():row['directions'][d]=[x['id'] for x in rec if re.search(pat,json.dumps(x['notes'],ensure_ascii=False))]
  rows.append(row)
 return {'method':'依主板块及具体笔记词语建立阅读覆盖索引；不是系统综述覆盖率或独立试验数','matrix':rows,'gaps':['cN1直接随机RT生存证据不足；PROPER招募不足','术后pN1的RT时机、ADT时长和照射范围随机证据有限','腹主动脉旁及其他M1a不能从盆腔随机研究直接外推','长期再照射累积剂量、晚期毒性及患者报告结局仍不足','待筛候选尚未全部人工审阅；Embase、Web of Science、知网、万方未接入']}
def validate_registry(reg):
 ids=set()
 for r in reg:
  assert r['id'] not in ids,'Registry duplicate';ids.add(r['id']);assert r.get('title') and r.get('screening'),'Bad registry row'
  assert 'abstract' not in r,'Raw abstract must not enter published registry'
 return True
def execute(mode='auto',replay=False):
 cfg=read(ROOT/'config/search.json');state=read(ROOT/'data/state.json',{'source_watermarks':{},'last_history_month':None});oldlib=read(ROOT/'data/library.json',[]);oldreg=read(ROOT/'data/registry.json',[]);status=read(ROOT/'data/status.json',{});stamp=now();runid=stamp.replace(':','-')+'-'+digest({'time':stamp})[:8]
 chosen='history' if mode=='history' or (mode=='auto' and (not oldreg or (cfg.get('monthly_history') and state.get('last_history_month')!=stamp[:7]))) else 'weekly'
 status.update(last_attempt=stamp,attempt_state='running');atomic(ROOT/'data/status.json',status)
 c=Client();logs=[];ok={'pubmed':False,'europepmc':False};pm={};ep={};metadata_errors={};selected=read(ROOT/'data/seeds.json')+read(ROOT/'data/manual/additions.json',[]);ids=[s['pmid'] for s in selected if s.get('pmid')]
 report={'id':runid,'started_at':stamp,'mode':'replay' if replay else chosen,'query_version':cfg['query_version'],'notes_policy':'自动更新保留笔记；来源变化则撤销内容已核对状态；候选不自动生成中文结论'}
 try:
  if replay:
   frozen=read(ROOT/'data/sources/frozen-input.json');assert frozen,'No frozen input for repeat';pm=frozen['pm'];ep=frozen['ep'];logs=frozen['queries'];ok=frozen['sources'];metadata_errors=frozen['metadata_errors']
  else:
   u,logs,ok=searches(c,cfg,chosen,state)
   if ok['pubmed']:
    try:pm=fetch_pm(c,sorted(u['pubmed']|set(ids)))
    except Exception as e:ok['pubmed']=False;metadata_errors['pubmed']=str(e);pm={}
   if ok['europepmc']:
    try:
     ep=u['europepmc'];selectedep=fetch_ep(c,ids);ep.update({'MED:'+k:v for k,v in selectedep.items()})
     assert set(ids).issubset(selectedep),'Incomplete selected EPMC metadata'
    except Exception as e:ok['europepmc']=False;metadata_errors['europepmc']=str(e);ep={}
   atomic(ROOT/'data/sources/frozen-input.json',{'pm':pm,'ep':ep,'queries':logs,'sources':ok,'metadata_errors':metadata_errors})
  report.update(queries=logs,sources=ok,metadata_errors=metadata_errors,metadata_count={'pubmed':len(pm),'europepmc':len(ep)})
  if not any(ok.values()):raise RuntimeError('All sources failed; retain previous reading library and registry')
  reg,conflicts=merge_registry(oldreg,pm,ep,stamp);validate_registry(reg)
  checks=read(ROOT/'data/sources/fulltext_checks.json',{})
  if not replay:
   report['crossref_versions']=refresh_versions(c,selected,cfg.get('version_checks_per_run',12))
   # Rotating verification queue; source restrictions never delete bibliographic records.
   todo=sorted(selected,key=lambda p:checks.get(p['id'],{}).get('checked_at',checks.get(p['id'],{}).get('verified_at','')))[:cfg.get('fulltext_checks_per_run',12)]
   epidx={m.get('pmid') or m.get('id'):m for m in ep.values() if m.get('source')=='MED'}
   for p in todo:
    previous=checks.get(p['id']);new=verify_one(c,p,epidx.get(p['pmid'],{}))
    if new['status']!='body_obtained' and previous and previous.get('status')=='body_obtained':new['previous_confirmed_body']={k:previous.get(k) for k in ['url','checked_at','verified_at','body_sha256','version']}
    checks[p['id']]=new
   atomic(ROOT/'data/sources/fulltext_checks.json',checks)
  else:epidx={m.get('pmid') or m.get('id'):m for m in ep.values() if m.get('source')=='MED'}
  if ok['pubmed'] and ok['europepmc']:
   lib=make_library(pm,epidx,checks,oldlib)
  else:lib=copy.deepcopy(oldlib) # Do not lower confidence from an unavailable source.
  validate(lib);changes=diff_records(oldlib,lib);rchanges=diff_records(oldreg,reg);libids={x['id'] for x in lib};counts=collections.Counter(x['screening'] for x in reg if x['id'] not in libids)
  snapshot={'schema_version':1,'topic':cfg['topic'],'created_at':stamp,'run_id':runid,'library':lib,'registry':reg,'conflicts':conflicts,'coverage':coverage(lib)}
  content_hash=digest({'library':stable(lib),'registry':stable(reg),'conflicts':conflicts});snapshot['content_hash']=content_hash
  # Persist the candidate before advancing any source cursor.
  atomic(ROOT/'data/candidates'/f'{runid}.json',snapshot)
  candidate=read(ROOT/'data/candidates'/f'{runid}.json');validate(candidate['library']);validate_registry(candidate['registry'])
  assert candidate['content_hash']==content_hash==digest({'library':stable(candidate['library']),'registry':stable(candidate['registry']),'conflicts':candidate['conflicts']}),'Candidate content hash mismatch'
  if changes['removed']:raise ValueError('Unexpected removal of curated reading records')
  if (ROOT/'data/current.json').exists():atomic(ROOT/'data/previous.json',read(ROOT/'data/current.json'))
  # One authoritative atomic pointer-sized snapshot. Other files are derived conveniences.
  atomic(ROOT/'data/current.json',candidate)
  atomic(ROOT/'data/library.json',lib);atomic(ROOT/'data/registry.json',reg);atomic(ROOT/'data/reports/coverage.json',snapshot['coverage'])
  for src,success in ok.items():
   if success:state['source_watermarks'][src]={'through':stamp,'persisted_run':runid,'query_version':cfg['query_version']}
  if all(ok.values()) and chosen=='history':state['last_history_month']=stamp[:7]
  state['current_hash']=content_hash;atomic(ROOT/'data/state.json',state)
  outcome='success_no_additions' if all(ok.values()) and not rchanges['added'] and not changes['added'] else 'success' if all(ok.values()) else 'partial_success'
  report.update(status=outcome,local_snapshot_validated=True,cloud_published=False,content_hash=content_hash,reading_changes=changes,candidate_changes=rchanges,counts={'reading':len(lib),'registry':len(reg),'pending':sum(v for k,v in counts.items() if k.startswith('pending')),'excluded':counts.get('excluded',0),'important':counts.get('important',0),'conflicts':len(conflicts)},screening_counts=dict(counts))
  status.update(attempt_state=outcome,last_local_validation=now(),current_hash=content_hash,last_run_id=runid,counts=report['counts'],new_candidates=len(rchanges['added']),updated_candidates=len(rchanges['updated']),new_reading=len(changes['added']),full_sources_success=all(ok.values()))
  # last_full_success and last_publish are only written by verified cloud publication receipt.
 except Exception as e:
  report.update(status='failed',local_snapshot_validated=False,cloud_published=False,error=str(e));status.update(attempt_state='failed',error=str(e))
 report['finished_at']=now();report['network']={'requests':len(c.events),'fresh':sum(x['status']=='ok' for x in c.events),'cache':sum(x['status']=='cache' for x in c.events),'failed':sum(x['status']=='failed' for x in c.events)}
 atomic(ROOT/'data/runs'/f'{runid}.json',report);atomic(ROOT/'data/reports/latest_run.json',report);atomic(ROOT/'data/status.json',status)
 print(json.dumps({k:report.get(k) for k in ['id','status','counts','network','error']},ensure_ascii=False),flush=True)
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['auto','history','weekly'],default='auto');p.add_argument('--replay',action='store_true');a=p.parse_args();r=execute(a.mode,a.replay)
 if r['status']=='failed':raise SystemExit(1)
