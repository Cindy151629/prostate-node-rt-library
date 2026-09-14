"""Only a verified HTTPS deployment can advance success timestamps."""
import argparse
from common import *
def receipt(outcome,url=None):
 old=read(ROOT/'data/publication-status.json',{});latest=read(ROOT/'data/reports/latest_run.json',{});snap=read(ROOT/'data/current.json',{});verification=read(ROOT/'data/deployment-verification.json',{});stamp=now()
 r={**old,'topic':read(ROOT/'config/search.json')['topic'],'last_attempt':stamp,'status':outcome,'run_id':latest.get('id'),'github_run_url':os.getenv('RUN_URL'),'verified_snapshot_hash':verification.get('content_hash')}
 if outcome=='published':
  assert verification.get('mode')=='HTTPS deployment' and verification.get('content_hash')==snap.get('content_hash'),'Unverified or stale publish cannot advance timestamps'
  assert verification.get('verified_at') and datetime.fromisoformat(stamp)-datetime.fromisoformat(verification['verified_at'])<__import__('datetime').timedelta(hours=1),'Stale verification receipt'
  r['last_publish']=verification['verified_at'];r['url']=url or verification['url'];r['status']='partial_success' if latest.get('status')=='partial_success' else latest.get('status','success')
  if latest.get('local_snapshot_validated') and all(latest.get('sources',{}).values()) and latest.get('sources'):r['last_full_success']=verification['verified_at']
 else:r['error']='Update, persistence, deployment or verification failed; previous successful timestamps retained.'
 atomic(ROOT/'data/publication-status.json',r);return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('outcome',choices=['published','failed']);p.add_argument('--url');a=p.parse_args();print(json.dumps(receipt(a.outcome,a.url),ensure_ascii=False))
