import copy,sys,tempfile,unittest,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from library import merge_registry,validate,source_identity
from fulltext import identify_html,verify_jats
from discovery import pm_search,ep_search
from update import diff_records,execute
import common,library,update,publication
class Fake:
 def __init__(self,rows):self.rows=iter(rows)
 def get(self,*a,**k):return next(self.rows)
class Tests(unittest.TestCase):
 def test_login_200_not_fulltext(self):
  p={'doi':'10.1/x','pmid':'7'};r=identify_html('<html>Log in to access this article. DOI 10.1/x</html>',p);self.assertFalse(r['body_confirmed'])
 def test_wrong_jats_identity(self):
  raw='<article><front><article-meta><article-id pub-id-type="pmid">9</article-id></article-meta></front><body><p>'+('x'*600)+'</p></body></article>'
  self.assertEqual(verify_jats(raw,{'pmid':'7'})['status'],'identity_conflict')
 def test_pm_incomplete_page(self):
  c=Fake([{'esearchresult':{'count':'3','idlist':['1','2']}},{'esearchresult':{'count':'3','idlist':[]}}]);self.assertRaises(ValueError,pm_search,c,'query')
 def test_ep_incomplete_cursor(self):
  c=Fake([{'hitCount':2,'resultList':{'result':[{'source':'MED','id':'1'}]},'nextCursorMark':'*'}]);self.assertRaises(ValueError,ep_search,c,'query')
 def test_full_pagination(self):
  c=Fake([{'esearchresult':{'count':'3','idlist':['1','2']}},{'esearchresult':{'count':'3','idlist':['3']}}]);self.assertEqual(pm_search(c,'query'),(['1','2','3'],3))
 def test_doi_conflict_quarantined(self):
  old=[{'id':'PMID1','pmid':'1','doi':'10.1/x','title':'A','sources':['PubMed']}];reg,conf=merge_registry(old,{'2':{'pmid':'2','doi':'https://doi.org/10.1/X','title':'B','abstract':''}}, {},'now');self.assertEqual(len(reg),1);self.assertEqual(len(conf),1)
 def test_similar_title_never_merged(self):
  rows={str(i):{'pmid':str(i),'title':'Identical title','doi':'10.1/'+str(i),'abstract':''} for i in [1,2]};reg,conf=merge_registry([],rows,{},'now');self.assertEqual(len(reg),2)
 def test_corrupt_candidate_rejected(self):
  self.assertRaises(AssertionError,validate,[]);self.assertRaises(AssertionError,validate,{'library':[]})
 def test_validation_identity_conflict(self):
  m={'pmid':'1','doi':'10.1/a','title':'First','authors':['A'],'journal':'J','year':'2026'};r=source_identity(m,{'id':'1','doi':'10.1/b','title':'Different','pubYear':'2026'},{'doi':'10.1/a'});self.assertEqual(r['status'],'field_review')
 def test_diff_ignores_check_timestamp_preserves_notes(self):
  a=[{'id':'1','notes':{'manual':'unchanged'},'checked_at':'old'}];b=copy.deepcopy(a);b[0]['checked_at']='new';self.assertEqual(diff_records(a,b)['updated'],[]);b[0]['notes']['manual']='edit';self.assertEqual(diff_records(a,b)['updated'],['1'])
 def test_source_failure_keeps_snapshot_and_watermark(self):
  real=common.ROOT
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'config').mkdir();(root/'data/manual').mkdir(parents=True)
   for rel in ['config/search.json','data/seeds.json','data/manual/additions.json','data/library.json','data/current.json','data/state.json','data/registry.json']:
    src=real/rel
    if src.exists():dst=root/rel;dst.parent.mkdir(exist_ok=True,parents=True);dst.write_bytes(src.read_bytes())
   before=(root/'data/current.json').read_bytes();water=(root/'data/state.json').read_bytes()
   class Offline:
    def __init__(self):self.events=[]
   with patch.object(update,'ROOT',root),patch.object(update,'Client',Offline),patch.object(update,'searches',return_value=({'pubmed':set(),'europepmc':{}},[],{'pubmed':False,'europepmc':False})):
    r=execute('weekly');self.assertEqual(r['status'],'failed')
   self.assertEqual(before,(root/'data/current.json').read_bytes());self.assertEqual(water,(root/'data/state.json').read_bytes())
 def test_unverified_publish_never_sets_success(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'config').mkdir();(root/'data').mkdir();(root/'config/search.json').write_text('{"topic":"t"}');(root/'data/current.json').write_text('{"content_hash":"x"}')
   with patch.object(publication,'ROOT',root):self.assertRaises(AssertionError,publication.receipt,'published')
 def test_manual_override_and_mappings_survive_rebuild(self):
  import shutil
  real=common.ROOT
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);shutil.copytree(real/'data/manual',root/'data/manual');shutil.copy2(real/'data/seeds.json',root/'data/seeds.json');(root/'data/sources').mkdir()
   shutil.copy2(real/'data/sources/crossref.json',root/'data/sources/crossref.json')
   rows=common.read(real/'data/library.json');target=rows[0]['id'];rows[0]['external_mappings']={'zotero':'KEEP-Z','obsidian':'KEEP-O'};rows[0]['manual_annotations']={'comment':'KEEP-C'}
   override={target:{'notes':{'limitations':'人工校正测试内容，仅存在于隔离测试目录，不得被自动元数据覆盖。'}}}
   common.atomic(root/'data/manual/overrides.json',override);before=(root/'data/manual/notes.json').read_bytes();ov=(root/'data/manual/overrides.json').read_bytes()
   pm={r['pmid']:{**r,'abstract':''} for r in rows if r.get('pmid')}
   with patch.object(library,'ROOT',root):rebuilt=library.make_library(pm,{}, {},rows)
   r=next(r for r in rebuilt if r['id']==target);self.assertEqual(r['notes']['limitations'],override[target]['notes']['limitations']);self.assertEqual(r['external_mappings']['zotero'],'KEEP-Z');self.assertEqual(r['manual_annotations']['comment'],'KEEP-C');self.assertEqual(before,(root/'data/manual/notes.json').read_bytes());self.assertEqual(ov,(root/'data/manual/overrides.json').read_bytes())
 def replay_fixture(self,root,sources):
  real=common.ROOT
  for rel in ['config/search.json','data/seeds.json','data/manual/additions.json','data/library.json','data/current.json','data/state.json','data/registry.json']:
   dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((real/rel).read_bytes())
  common.atomic(root/'data/sources/frozen-input.json',{'pm':{},'ep':{},'queries':[],'sources':sources,'metadata_errors':{}})
 def test_partial_source_does_not_advance_failed_watermark(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.replay_fixture(root,{'pubmed':True,'europepmc':False});water=common.read(root/'data/state.json')['source_watermarks']['europepmc']
   with patch.object(update,'ROOT',root):r=execute('weekly',True)
   self.assertEqual(r['status'],'partial_success');self.assertEqual(common.read(root/'data/state.json')['source_watermarks']['europepmc'],water)
 def test_tampered_valid_candidate_keeps_previous_snapshot(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.replay_fixture(root,{'pubmed':True,'europepmc':True});before=(root/'data/current.json').read_bytes();water=(root/'data/state.json').read_bytes();rows=common.read(root/'data/library.json')
   def tamper(path,value):
    if 'candidates' in Path(path).parts:
     value=copy.deepcopy(value);value['library'][0]['notes']['findings'][0]+=' TAMPERED'
    common.atomic(path,value)
   with patch.object(update,'ROOT',root),patch.object(update,'atomic',tamper),patch.object(update,'make_library',return_value=rows):r=execute('weekly',True)
   self.assertEqual(r['status'],'failed');self.assertIn('hash mismatch',r['error']);self.assertEqual(before,(root/'data/current.json').read_bytes());self.assertEqual(water,(root/'data/state.json').read_bytes())
 def test_long_outage_window_and_independent_field_failure(self):
  import discovery
  class Fields:
   def get(self,url,*a,**kw):
    if 'einfo' in url:return {'einforesult':{'dbinfo':[{'fieldlist':[{'name':x} for x in ['PDAT','EDAT','MDAT','CRDT']]}]}}
    raise RuntimeError('EPMC unavailable')
  cfg={'lookback_days':90,'queries':[{'id':'broad','pubmed':'query','europepmc':'query'}]};water={'source_watermarks':{'pubmed':{'through':'2025-01-01T00:00:00+00:00'}}}
  with patch.object(discovery,'pm_search',return_value=(['1'],1)),patch.object(discovery,'now',return_value='2026-09-14T00:00:00+00:00'):
   u,logs,ok=discovery.searches(Fields(),cfg,'weekly',water)
  self.assertTrue(ok['pubmed']);self.assertFalse(ok['europepmc']);self.assertEqual(logs[0]['from'],'2024-10-03');self.assertEqual(u['pubmed'],{'1'})
 def test_republish_preserves_source_success_timestamp(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for rel,value in {'config/search.json':{'topic':'t'},'data/current.json':{'content_hash':'x'},'data/reports/latest_run.json':{'id':'same','local_snapshot_validated':True,'sources':{'pubmed':True,'europepmc':True},'finished_at':'2026-01-01T00:00:00+00:00'},'data/publication-status.json':{'last_full_success':'2026-01-01T00:01:00+00:00','run_id':'same'},'data/deployment-verification.json':{'content_hash':'x','mode':'HTTPS deployment','verified_at':common.now(),'url':'https://example.invalid'}}.items():common.atomic(root/rel,value)
   with patch.object(publication,'ROOT',root):r=publication.receipt('published')
   self.assertEqual(r['last_full_success'],'2026-01-01T00:01:00+00:00');self.assertEqual(r['last_source_complete_at'],'2026-01-01T00:00:00+00:00')
if __name__=='__main__':unittest.main()
