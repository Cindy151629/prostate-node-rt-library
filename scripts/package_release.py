"""Create a reviewed allowlist release; do not publish raw articles or local access caches."""
import shutil,sys
from common import *
from persist import SELECT
def package(dest):
 dest=Path(dest).resolve();assert dest!=ROOT;dest.mkdir(parents=True,exist_ok=True)
 for rel in ['scripts','tests','config','web','public','.github','README.md','.gitignore']:
  src=ROOT/rel;target=dest/rel
  if src.is_dir():shutil.copytree(src,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  else:shutil.copy2(src,target)
 for rel in SELECT+['seeds.json','manual','sources/crossref.json','sources/corrections.json']:
  src=ROOT/'data'/rel;target=dest/'data'/rel
  if not src.exists():continue
  target.parent.mkdir(parents=True,exist_ok=True)
  if src.is_dir():shutil.copytree(src,target,dirs_exist_ok=True)
  else:shutil.copy2(src,target)
 for rel in ['seeds.json','manual/additions.json']:
  p=dest/'data'/rel
  atomic(p,[{k:v for k,v in x.items() if k in ['id','seed_id','seed_title','pmid','doi','pmcid','links']} for x in read(p)])
 forbidden=[p for p in dest.rglob('*') if p.is_file() and (p.suffix in ['.pdf','.xml'] or any(x in p.parts for x in ['cache','fulltext','publisher']))]
 assert not forbidden,'Unexpected raw article in release'
 return dest
if __name__=='__main__':print(package(sys.argv[1]))
