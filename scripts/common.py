"""Shared primitives; network content is data, never executable instructions."""
import json,os,time,hashlib,urllib.request,urllib.parse,urllib.error,threading,re,html,tempfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def now():return datetime.now(timezone.utc).isoformat()
def read(path,default=None):return json.loads(Path(path).read_text()) if Path(path).exists() else default
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)
 with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False,encoding='utf-8') as f:f.write(text);temp=f.name
 os.replace(temp,path)
def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def doi(s):return re.sub(r'^https?://(?:dx\.)?doi.org/','',s or '',flags=re.I).strip().lower()
def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',html.unescape(s or ''))).strip()
def safeurl(url):return bool(re.match(r'^https://[^\s<>]+$',url or ''))
class Client:
 def __init__(self,cache=None,refresh=False):
  self.cache=Path(cache or ROOT/'data/sources/cache');self.cache.mkdir(parents=True,exist_ok=True);self.refresh=refresh;self.lock=threading.Lock();self.last={};self.events=[]
 def get(self,url,params=None,fmt='json',ttl=86400*7):
  if params:url+='?'+urllib.parse.urlencode(params)
  key=hashlib.sha256(url.encode()).hexdigest();p=self.cache/(key+'.'+('json' if fmt=='json' else 'txt'));meta=self.cache/(key+'.meta.json')
  if p.exists() and not self.refresh and time.time()-p.stat().st_mtime<ttl:
   self.events.append({'url':url,'status':'cache','retrieved_at':read(meta,{}).get('retrieved_at')});return read(p) if fmt=='json' else p.read_text()
  host=urllib.parse.urlparse(url).netloc;err=None
  for attempt in range(4):
   with self.lock:
    delay=max(0,.38-(time.monotonic()-self.last.get(host,0)));time.sleep(delay);self.last[host]=time.monotonic()
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'ProstateNodeRT-LiteratureLibrary/1.0 (research metadata; respectful rate limit)','Accept':'application/json' if fmt=='json' else '*/*'})
    with urllib.request.urlopen(req,timeout=35) as resp:raw=resp.read().decode('utf-8',errors='replace');final=resp.url;ct=resp.headers.get('Content-Type','')
    value=json.loads(raw) if fmt=='json' else raw
    atomic(p,value);atomic(meta,{'url':url,'final_url':final,'content_type':ct,'retrieved_at':now(),'sha256':hashlib.sha256(raw.encode()).hexdigest()});self.events.append({'url':url,'status':'ok','retrieved_at':now()});return value
   except Exception as e:
    err=e;code=getattr(e,'code',None)
    if code and code not in [429,500,502,503,504]:break
    if attempt<3:time.sleep(min(2**attempt,8))
  self.events.append({'url':url,'status':'failed','error':str(err),'attempted_at':now()});raise RuntimeError(f'{url}: {err}')
