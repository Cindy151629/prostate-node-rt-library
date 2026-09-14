"""Store only bibliography, Chinese notes and logs on the data branch, never raw bodies."""
import shutil,subprocess,sys
from common import *
SELECT=['current.json','previous.json','library.json','registry.json','state.json','status.json','publication-status.json','deployment-verification.json','reports','runs','sources/fulltext_checks.json','sources/crossref_relations.json']
def run(*a):return subprocess.run(a,check=True,capture_output=True,text=True).stdout.strip()
def persist(dest):
 dest=Path(dest).resolve();dest.mkdir(exist_ok=True,parents=True)
 for rel in SELECT:
  src=ROOT/'data'/rel;target=dest/rel
  if not src.exists():continue
  target.parent.mkdir(exist_ok=True,parents=True)
  if src.is_dir():shutil.copytree(src,target,dirs_exist_ok=True)
  else:shutil.copy2(src,target)
 return dest
if __name__=='__main__':persist(sys.argv[1])
