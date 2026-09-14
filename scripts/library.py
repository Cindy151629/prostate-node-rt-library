"""Source-grounded reading library. Manual notes/overrides are read-only inputs."""
import difflib,collections,unicodedata
from common import *
SECTIONS=read(ROOT/'config/search.json')['sections']
def norm(s):return re.sub(r'[^\w]','',unicodedata.normalize('NFKD',clean(s)).lower())
def dateparts(d):
 if not d:return None
 months={x:i+1 for i,x in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}
 y=d.get('Year');mo=d.get('Month');day=d.get('Day')
 if not y:return d.get('MedlineDate') or None
 if not mo:return y
 mo=str(months.get(mo,mo))
 if not mo.isdigit():return y+' '+mo
 return y+'-'+mo.zfill(2)+('-'+str(day).zfill(2) if day else '')
def pm_from_ep(e):
 ji=e.get('journalInfo',{});j=ji.get('journal',{})
 return {'pmid':e.get('pmid') or (e['id'] if e.get('source')=='MED' else ''),'doi':doi(e.get('doi')),'pmcid':e.get('pmcid',''),'title':clean(e.get('title','')),'authors':[clean(x) for x in e.get('authorString','').rstrip('.').split(', ') if x],'journal':j.get('title',''),'year':e.get('pubYear',''),'abstract':clean(e.get('abstractText','')),'types':e.get('pubTypeList',{}).get('pubType',[]),'publication_date_parts':{},'online_date_parts':[],'dates':{},'corrections':[],'first_publication':e.get('firstPublicationDate')}
def bibliog(m):
 return {k:v for k,v in m.items() if k not in ['abstract','abstract_sections']}
def source_identity(m,e,s):
 fields={};errors=[]
 if s.get('doi') and doi(s['doi'])!=doi(m.get('doi')):errors.append('起始DOI与官方记录不一致')
 if e:
  fields['title']=difflib.SequenceMatcher(None,norm(m['title']),norm(e.get('title',''))).ratio()>=.96
  fields['doi']=not e.get('doi') or doi(e['doi'])==doi(m.get('doi'))
  fields['pmid']=str(e.get('pmid') or e.get('id'))==m.get('pmid')
  ej=e.get('journalInfo',{}).get('journal',{}).get('title','');fields['journal']=not ej or norm(ej)==norm(m.get('journal',''))
  ea=[norm(a.get('collectiveName') or (a.get('lastName','')+' '+a.get('initials','')).strip()) for a in e.get('authorList',{}).get('author',[])];pa=[norm(a) for a in m.get('authors',[])]
  fields['authors']=None if not ea else ea==pa
  fields['year']=str(e.get('pubYear',''))==str(m.get('year',''))
  # Different collective names/online vs print years remain visible field warnings, not guessed corrections.
  errors += [k+'字段需核对' for k,v in fields.items() if v is False]
 return {'status':'official_match' if not errors else 'field_review','fields':fields,'issues':errors,'sources':(['PubMed','Europe PMC（共享MEDLINE）'] if e else ['PubMed']) if m.get('pmid') else ['Crossref','出版社PDF'],'checked_at':now()}
def research_type(m,n):
 t=(m['title']+' '+m.get('abstract','')).lower();types=' '.join(m.get('types',[])).lower()
 if n.get('section')=='F' or 'study protocol' in t or 'protocol for' in t:return '试验方案/设计'
 if 'meta-analysis' in types or 'systematic review' in t:return '系统综述/荟萃分析'
 if 'guideline' in t or 'recommendations' in m['title'].lower():return '指南/共识'
 if 'review' in types:return '叙述综述'
 if re.search('dosimetric|contouring|delineation|lymph node atlas|planning study|quality assurance|interobserver',m['title'],re.I):return '靶区/剂量学/质控'
 if 'post hoc' in t or 'post-hoc' in t:return '事后/次级分析'
 if 'randomized controlled trial' in types or re.search(r'phase (?:2|ii|3|iii).*random|randomi[sz]ed.*trial',m['title'],re.I):return '随机试验/报告'
 if 'phase i' in t or 'phase 1' in t:return '早期前瞻试验'
 if 'retrospect' in t or '回顾' in n.get('design','') or '数据库' in n.get('design',''):return '观察性研究'
 if 'prospective' in t or '前瞻' in n.get('design',''):return '前瞻性单臂/队列'
 return '其他/设计需核对'
def classify_pending(m):
 t=m.get('title','').lower();a=m.get('abstract','').lower();txt=t+' '+a
 if any(x in ' '.join(m.get('types',[])).lower() for x in ['retracted publication','published erratum','retraction of publication']) or re.search(r'^(correction|erratum|retraction)',t):return 'important','更正/撤稿或版本关联，需与原文核对'
 if not re.search(r'prostat',txt):return 'excluded','未识别前列腺癌研究对象；自动初筛排除，可复核'
 if re.search(r'^(re:|reply|commentary|letter|words of wisdom)',t):return 'pending','来信/评论，保留为论证背景候选'
 if re.search(r'node.negative|\bn0\b',t) and not re.search(r'node.positive|\bn1\b|nodal recur',t):return 'excluded','题名主要为N0/预防照射，未核实结阳性专属结果'
 if re.search(r'nomogram|predict.*lymph node|diagnostic.*accuracy|lymph node dissection',t) and not re.search(r'radiother|irradiat|radiation|SBRT',t):return 'excluded','题名以预测/诊断/手术为主，未核实放疗问题'
 if re.search(r'radiother|irradiat|radiation therapy|sbrt|sabr',t) and re.search(r'nod[ae]|lymph|pn1|cn1',t) and a:return 'pending_priority','身份题录及主题词规则通过；实际人群、内容尚待逐篇精读'
 return 'pending','交集检索命中，尚不能凭词语确定实际人群/干预'
def merge_registry(previous,pm,ep,stamp):
 """No fuzzy title merge. Inconsistent PMID/DOI pair is quarantined."""
 reg={x['id']:x for x in previous};conflicts=[];doi_idx={doi(x.get('doi')):x['id'] for x in previous if x.get('doi')}
 inputs=[(m,'PubMed') for m in pm.values()]+[(pm_from_ep(e),'Europe PMC') for e in ep.values()]
 for m,src in inputs:
  if not m.get('title'):continue
  pid=m.get('pmid');d=doi(m.get('doi'));sid='PMID'+pid if pid else 'DOI'+hashlib.sha256(d.encode()).hexdigest()[:16] if d else src+digest(m)[:16]
  old=reg.get(sid)
  if d in doi_idx and doi_idx[d]!=sid:
   peer=reg[doi_idx[d]]
   if pid and peer.get('pmid') and pid!=peer['pmid']:conflicts.append({'id':sid,'doi':d,'other':peer['id'],'reason':'相同DOI不同PMID，不自动合并'});continue
   sid=peer['id'];old=peer
  if old and old.get('doi') and d and old['doi']!=d:conflicts.append({'id':sid,'doi':d,'previous_doi':old['doi'],'reason':'同PMID的DOI变化，隔离核验'});continue
  # Prefer native PubMed over MEDLINE mirror. EPMC presence and dates still tracked.
  disposition,reason=classify_pending(m)
  if old and src=='Europe PMC' and 'PubMed' in old.get('sources',[]):
   old['sources']=sorted(set(old['sources']+[src]));continue
  b=bibliog(m);b.update(id=sid,doi=d,sources=sorted(set((old or {}).get('sources',[])+[src])),first_discovered=(old or {}).get('first_discovered',stamp),abstract_sha256=hashlib.sha256(m.get('abstract','').encode()).hexdigest(),screening=disposition,screening_reason=reason)
  if old and b['abstract_sha256']==hashlib.sha256(b'').hexdigest():b['abstract_sha256']=old.get('abstract_sha256',b['abstract_sha256'])
  reg[sid]=b
  if d:doi_idx[d]=sid
 return sorted(reg.values(),key=lambda x:x['id']),conflicts
def make_library(pm,ep,checks,previous=None):
 previous={x['id']:x for x in (previous or [])};seeds=read(ROOT/'data/seeds.json')+read(ROOT/'data/manual/additions.json',[]);notes=read(ROOT/'data/manual/notes.json',{});overrides=read(ROOT/'data/manual/overrides.json',{});cross=read(ROOT/'data/sources/crossref.json',{});out=[]
 for s in seeds:
  m=pm.get(s.get('pmid'));e=ep.get(s.get('pmid'),{})
  if not m:
   cr=cross.get(s.get('doi'),{});dp=cr.get('published',{}).get('date-parts',[[]])[0];m={'title':cr.get('title',[s['seed_title']])[0],'authors':[a.get('family','')+' '+a.get('given','') for a in cr.get('author',[])],'journal':cr.get('container-title',[''])[0],'year':str(dp[0]) if dp else '', 'doi':s.get('doi'),'pmid':'','pmcid':'','publication_date_parts':dict(zip(['Year','Month','Day'],map(str,dp))),'online_date_parts':[dict(zip(['Year','Month','Day'],map(str,dp)))],'abstract':'','types':['Journal Article'],'dates':{},'corrections':[]}
  n=notes.get(s['id']);assert n, 'Missing content note '+s['id'];n=dict(n);sec=n.get('section',s['seed_id'][0]);assert sec in SECTIONS
  r=bibliog(m);r.update(id=s['id'],seed_id=s['seed_id'],seed_origin='DOCX起始目录' if not s['seed_id'].startswith('X') else '基础检索补漏',section=sec,zh_title=n['zh_title'],notes=n,article_url='https://pubmed.ncbi.nlm.nih.gov/'+m['pmid']+'/' if m.get('pmid') else 'https://doi.org/'+m['doi'],publication_date=dateparts(m.get('publication_date_parts')),first_online_date=next(iter([dateparts(v) for v in m.get('online_date_parts',[]) if v]),None),first_publication_date=e.get('firstPublicationDate'),added_at=previous.get(s['id'],{}).get('added_at',now()),first_discovered=previous.get(s['id'],{}).get('first_discovered',now()),inclusion='supporting' if sec=='E' else 'core',research_type=research_type(m,{**n,'section':sec}),topic_note=n['question'])
  t=(m['title']+' '+m.get('abstract','')).lower()
  rt=[v for k,v in [('sbrt|sabr|stereotactic','SBRT/SABR'),('enrt|enrt|elective nodal|whole.pelvi|extended.field|whole pelvi','ENRT/WPRT'),('imrt|intensity.modulated','IMRT'),('vmat|volumetric','VMAT'),('brachy','近距离治疗'),('re.?irradiat|再照射','再照射'),('proton','质子')] if re.search(k,t+' '+n['design'])]
  node=n.get('node_site') or ('含非区域结/M1a，构成见笔记' if re.search('paraaort|para-aort|m1a|common iliac|extrapelvic|retroperitone',t) else '盆腔/区域结' if re.search('pelvic|cn1|pn1|regional',t) else '部位构成见笔记')
  scenario='初诊根治' if sec=='A' else '术后pN1' if sec=='B' else '复发/持续' if sec=='C' else '跨情境/需按人群查看'
  r.update(rt_modalities=rt or ['RT/细节见笔记'],node_site=node,clinical_scenario=scenario,population=n['design'],population_flag=n.get('population_flag'),trial=n.get('trial',''),tags=list(dict.fromkeys([scenario,node,r['research_type']]+rt+([n['trial']] if n.get('trial') else []))))
  ident=source_identity(m,e,s);ft=checks.get(s['id'],{'status':'not_checked','reason':'尚未核查'});ft=dict(ft);ft['body_confirmed']=ft.get('status')=='body_obtained'
  if s['seed_id']=='G003':ft['version']='出版社版本；机构仓储公开副本'
  flags=[x for x in [n.get('population_flag')] if x and re.search('冲突|疑点|不一致|待核',x)]
  if re.search('retracted publication|retraction of publication',' '.join(m.get('types',[])),re.I):flags.append('官方标记撤稿/撤稿公告；不得作为未经撤回的有效研究引用')
  if s['seed_id'] in ['C011','C034']:flags.append('摘要内部文字/终点不一致，需正文复核')
  src_changed=n.get('source_level')=='abstract' and n.get('source_sha256')!=hashlib.sha256(m.get('abstract','').encode()).hexdigest()
  r['verification']={'identity':ident,'fulltext':ft,'topic':{'status':'review_needed' if flags else 'source_screened','basis':n['design'],'issues':flags,'reviewer':'AI按来源筛选；未人工复核'},'content':{'status':'source_changed' if src_changed else 'source_checked_with_issues' if flags else 'source_checked','level':n['source_level'],'human_verified':False,'source_url':n['source_url'],'source_location':n['source_location'],'reviewed_at':n['reviewed_at'],'limitations':'依据摘要/指定正文段落整理；不代表整篇全文、图表和补充材料均已精读'}}
  r['external_mappings']=previous.get(s['id'],{}).get('external_mappings',{'zotero':None,'obsidian':None});r['manual_annotations']=previous.get(s['id'],{}).get('manual_annotations',{})
  # Deep patch only explicit human edits; update never writes the source override file.
  def patch(a,b):
   for k,v in b.items():
    if isinstance(v,dict) and isinstance(a.get(k),dict):patch(a[k],v)
    else:a[k]=v
  patch(r,overrides.get(s['id'],{}));out.append(r)
 id_by_seed={r['seed_id']:r['id'] for r in out}
 versions=read(ROOT/'data/sources/crossref_relations.json',{})
 for r in out:
  r['related_ids']=[id_by_seed[k] for k in r['notes'].get('related_seeds',[]) if k in id_by_seed]
  if r['id'] in versions:r['version_check']=versions[r['id']]
 validate(out);return out
def validate(records):
 assert records and isinstance(records,list),'Invalid empty/non-list candidate'
 seen=set();ds=set()
 for r in records:
  assert r['id'] not in seen,'Duplicate stable id';seen.add(r['id']);d=doi(r.get('doi'))
  assert not d or d not in ds,'Duplicate DOI';ds.add(d)
  for f in ['title','authors','journal','year','section','notes','verification','added_at']:assert r.get(f),f+' missing: '+r['id']
  assert r['section'] in SECTIONS
  n=r['notes'];assert len(n['design'])>=15 and n['findings'] and len(n['limitations'])>=15,'Empty/placeholder note'
  assert safeurl(r['article_url']) and safeurl(n['source_url']),'Unsafe article URL'
  assert r['verification']['content']['human_verified'] is False or r['id'] in read(ROOT/'data/manual/overrides.json',{}),'Unsubstantiated human verification'
 return True
if __name__=='__main__':
 pm=read(ROOT/'data/sources/pubmed.json');ep=read(ROOT/'data/sources/epmc.json');checks=read(ROOT/'data/sources/fulltext_checks.json');out=make_library(pm,ep,checks,read(ROOT/'data/library.json',[]));atomic(ROOT/'data/library.json',out);print('library',len(out),collections.Counter(r['verification']['identity']['status'] for r in out))
