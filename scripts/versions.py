"""Rotate Crossref-deposited version/correction checks; absence is not proof of no update."""
from common import *
def refresh(client,selected,limit=12):
 records=read(ROOT/'data/sources/crossref_relations.json',{});events=[]
 for p in sorted(selected,key=lambda p:records.get(p['id'],{}).get('checked_at',''))[:limit]:
  url='https://api.crossref.org/works/'+urllib.parse.quote(p['doi'],safe='')
  try:
   m=client.get(url)['message'];assert doi(m['DOI'])==doi(p['doi']),'Crossref DOI mismatch'
   records[p['id']]={'status':'checked','checked_at':now(),'url':url,'doi':doi(m['DOI']),'title':m.get('title',[]),'type':m.get('type'),'relations':m.get('relation',{}),'updates':m.get('update-to',[]),'note':'仅记录Crossref已登记关系；空关系不能证明没有更正、撤稿或后续版本'}
   events.append({'id':p['id'],'status':'checked'})
  except Exception as e:
   events.append({'id':p['id'],'status':'failed','error':str(e)})
 atomic(ROOT/'data/sources/crossref_relations.json',records)
 return {'checks':events,'checked_total':len(records),'selected_total':len(selected),'complete':len(records)==len(selected)}
