import xml.etree.ElementTree as ET,re
from common import *
NCBI='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EPMC='https://www.ebi.ac.uk/europepmc/webservices/rest/'
def text(e,path):return ''.join(e.find(path).itertext()).strip() if e.find(path) is not None else ''
def pubmed_parse(xml):
 root=ET.fromstring(xml)
 if root.find('ERROR') is not None:raise ValueError(text(root,'ERROR'))
 out={}
 for a in root.findall('.//PubmedArticle'):
  m=a.find('MedlineCitation');p=a.find('MedlineCitation/Article');pmid=text(m,'PMID');ab=[]
  for x in p.findall('.//Abstract/AbstractText'):ab.append({'label':x.get('Label',''),'text':''.join(x.itertext())})
  ids={x.get('IdType'):x.text for x in a.findall('PubmedData/ArticleIdList/ArticleId')};date={x.tag:x.text for x in p.findall('Journal/JournalIssue/PubDate/*')};online=[{x.tag:x.text for x in d} for d in p.findall('ArticleDate') if d.get('DateType')=='Electronic'];history={h.get('PubStatus'):'-'.join(text(h,k) for k in ['Year','Month','Day']) for h in a.findall('PubmedData/History/PubMedPubDate')}
  authors=[(text(x,'LastName')+' '+text(x,'Initials')).strip() or text(x,'CollectiveName') for x in p.findall('AuthorList/Author')]
  out[pmid]={'pmid':pmid,'title':clean(text(p,'ArticleTitle')),'authors':authors,'journal':text(p,'Journal/Title'),'journal_abbr':text(p,'Journal/ISOAbbreviation'),'year':date.get('Year') or (re.search(r'\d{4}',date.get('MedlineDate','')) or [''])[0],'publication_date_parts':date,'online_date_parts':online,'dates':history,'revision_date':'-'.join(text(m,'DateRevised/'+k) for k in ['Year','Month','Day']),'doi':doi(ids.get('doi','')),'pmcid':ids.get('pmc',''),'abstract_sections':ab,'abstract':'\n'.join((s['label']+': ' if s['label'] else '')+s['text'] for s in ab),'types':[x.text for x in p.findall('PublicationTypeList/PublicationType')],'corrections':[{'type':c.get('RefType'),'pmid':text(c,'PMID'),'citation':text(c,'RefSource'),'note':text(c,'Note')} for c in m.findall('CommentsCorrectionsList/CommentsCorrections')],'volume':text(p,'Journal/JournalIssue/Volume'),'issue':text(p,'Journal/JournalIssue/Issue'),'pages':text(p,'Pagination/MedlinePgn') or text(p,'ELocationID')}
 for a in root.findall('.//PubmedBookArticle'):
  p=a.find('BookDocument');pmid=text(p,'PMID')
  out[pmid]={'pmid':pmid,'title':clean(text(p,'ArticleTitle') or text(p,'Book/BookTitle')),'authors':[(text(x,'LastName')+' '+text(x,'Initials')).strip() for x in p.findall('AuthorList/Author')],'journal':text(p,'Book/BookTitle'),'year':text(p,'Book/PubDate/Year'),'doi':'','pmcid':'','abstract':clean(text(p,'Abstract')),'abstract_sections':[],'types':['Book Chapter'],'corrections':[],'dates':{},'revision_date':'','publication_date_parts':{},'online_date_parts':[]}
 return out
def fetch_pm(client,ids):
 out={}
 for i in range(0,len(ids),100):
  wanted=ids[i:i+100];params={'db':'pubmed','id':','.join(wanted),'retmode':'xml'}
  if os.getenv('NCBI_API_KEY'):params['api_key']=os.environ['NCBI_API_KEY']
  # Do not include secret-bearing request URLs in persisted logs.
  if 'api_key' in params:params.pop('api_key')
  d=pubmed_parse(client.get(NCBI+'efetch.fcgi',params,fmt='text'));out.update(d)
  missing=set(wanted)-set(d)
  if missing:raise ValueError('PubMed incomplete batch: '+str(sorted(missing)))
 return out
def fetch_ep(client,ids):
 out={}
 for i in range(0,len(ids),75):
  query='SRC:MED AND ('+' OR '.join('EXT_ID:'+x for x in ids[i:i+75])+')'
  d=client.get(EPMC+'search',{'query':query,'format':'json','resultType':'core','pageSize':1000});out.update({x['id']:x for x in d['resultList']['result']})
  if len(d['resultList']['result'])!=d['hitCount']:raise ValueError('EPMC metadata pagination incomplete')
 return out
def retrieve_seeds():
 client=Client();seeds=read(ROOT/'data/seeds.json');ids=[s['pmid'] for s in seeds if s['pmid']]
 pm=fetch_pm(client,ids);atomic(ROOT/'data/sources/pubmed.json',pm);print('PubMed',len(pm),flush=True)
 ep=fetch_ep(client,ids);atomic(ROOT/'data/sources/epmc.json',ep);print('Europe PMC',len(ep),flush=True)
 cross={}
 for s in seeds:
  if not s['pmid'] or doi(pm[s['pmid']]['doi'])!=doi(s['doi']):
   try:cross[s['doi']]=client.get('https://api.crossref.org/works/'+urllib.parse.quote(s['doi'],safe=''))['message']
   except Exception as e:cross[s['doi']]={'error':str(e)}
 atomic(ROOT/'data/sources/crossref.json',cross);atomic(ROOT/'data/reports/seed_retrieval.json',{'time':now(),'pubmed':len(pm),'epmc':len(ep),'events':client.events})
if __name__=='__main__':retrieve_seeds()
