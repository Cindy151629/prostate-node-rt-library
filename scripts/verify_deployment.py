"""Verify actual deployed manifest, HTML bytes, and embedded reading data."""
import argparse,re,urllib.request,time
from common import *

def verify(base,expected=None):
 expected=expected or read(ROOT/'public/manifest.json');base=base.rstrip('/')+'/';nonce='?verify='+str(time.time_ns())
 def get(path):
  with urllib.request.urlopen(urllib.request.Request(base+path+nonce,headers={'Cache-Control':'no-cache'}),timeout=35) as r:return r.read()
 manifest=json.loads(get('manifest.json'));html=get('index.html');embedded=re.search(rb'<script id="appdata" type="application/json">(.*?)</script>',html,re.S)
 assert embedded,'No website data loader found';data=json.loads(embedded.group(1))
 assert manifest['content_hash']==expected['content_hash'],'Stale deployment manifest'
 assert hashlib.sha256(html).hexdigest()==manifest['html_sha256']==expected['html_sha256'],'Stale/mismatched deployed HTML'
 assert data['content_hash']==expected['content_hash'],'HTML reads different data'
 assert len(data['library'])==expected['reading_count'],'Deployed count mismatch'
 assert all(r.get('notes',{}).get('findings') for r in data['library']),'Missing deployed content notes'
 return {'verified_at':now(),'url':base,'content_hash':manifest['content_hash'],'reading_count':len(data['library']),'html_sha256':manifest['html_sha256'],'mode':'HTTPS deployment' if base.startswith('https://') else 'localhost test only'}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('url');args=a.parse_args();last=None
 for attempt in range(6):
  try:
   r=verify(args.url);atomic(ROOT/'data/deployment-verification.json',r);print(json.dumps(r));break
  except Exception as e:
   last=e
   if attempt==5:raise
   time.sleep(10)
