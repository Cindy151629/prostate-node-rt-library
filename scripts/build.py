"""Build offline-capable HTML from the authoritative validated snapshot."""
from common import *
from library import validate
from update import validate_registry,coverage
import shutil

def build():
 snap=read(ROOT/'data/current.json');assert snap,'Run update before build';validate(snap['library']);validate_registry(snap['registry'])
 cfg=read(ROOT/'config/search.json');s=read(ROOT/'data/status.json',{});receipt=read(ROOT/'data/publication-status.json',{})
 if receipt.get('last_publish'):s.update({k:receipt[k] for k in ['last_publish','last_full_success'] if receipt.get(k)})
 data={**snap,'config':cfg,'status':s,'baseline':read(ROOT/'data/reports/baseline_search.json',{}),'latest_run':read(ROOT/'data/reports/latest_run.json',{}),'acceptance':read(ROOT/'data/reports/acceptance.json',{'cloud_deployed':False,'scheduled_event_observed':False})}
 # Raw downloaded abstracts/full text are never embedded or copied into the public site.
 for r in data['registry']:r.pop('abstract',None)
 raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
 template=(ROOT/'web/template.html').read_text();html=template.replace('__APP_DATA__',raw);dest=ROOT/'public';dest.mkdir(exist_ok=True)
 atomic(dest/'index.html',html);atomic(dest/'library.json',snap['library']);atomic(dest/'registry.json',snap['registry']);atomic(dest/'manifest.json',{'topic':cfg['topic'],'run_id':snap['run_id'],'content_hash':snap['content_hash'],'reading_count':len(snap['library']),'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'data_source':'validated embedded snapshot','last_attempt':s.get('last_attempt'),'full_sources_success':s.get('full_sources_success',False)});atomic(dest/'.nojekyll','');print('built',len(snap['library']),'notes',len(html.encode()),'bytes')
if __name__=='__main__':build()
