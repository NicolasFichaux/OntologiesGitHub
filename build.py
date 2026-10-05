"""Builds dist/earth-data-navigator.html from page.html, the data folder and the tables of ../local_app/taxonomy.
Run: python build.py   (from anywhere)."""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APP=os.path.join(HERE,'..','local_app'); DATA=os.path.join(HERE,'data')
OUT=os.environ.get('NAV_OUT', os.path.join(HERE,'dist','earth-data-navigator.html'))
os.makedirs(os.path.dirname(OUT), exist_ok=True); os.chdir(DATA)
import json, csv, datetime, re
tax=json.load(open(APP+'/taxonomy/earsc_taxonomy.json'))
cols=json.load(open('hda_cols.json'))
links=list(csv.DictReader(open(APP+'/taxonomy/collection_service_links.csv',encoding='utf-8'),delimiter=';'))
import base64
THUMBS=json.load(open('thumbs.json')); WMS=json.load(open('wms.json')); T=[]; TIDX={}
META=json.load(open(APP+'/taxonomy/collection_meta.json',encoding='utf-8'))
def _short(t,n=150): return t if len(t)<=n else t[:n-1]+'…'

cidx={}; C=[]
for c in cols:
    ti=(c.get('extent',{}).get('temporal',{}).get('interval') or [[None,None]])[0]
    cidx[c['id']]=len(C)
    th=THUMBS.get(((c.get('assets') or {}).get('thumbnail') or {}).get('href'))
    if th and th not in TIDX:
        TIDX[th]=len(T); T.append('data:image/jpeg;base64,'+base64.b64encode(open(th,'rb').read()).decode())
    C.append({"id":c['id'],"t":c.get('title',''),"o":int(any(l.get('rel')=='retrieve' for l in c.get('links',[]))),
              "s":(ti[0] or '')[:10],"e":(ti[1] or '')[:10],"th":TIDX.get(th) if th else None,"w":WMS.get(c['id'])})
    bb=((c.get('extent',{}).get('spatial',{}).get('bbox') or [None])[0])
    if bb and len(bb)==4 and all(isinstance(x,(int,float)) for x in bb):
        w_,s_,e_,n_=bb
        valid = -180<=w_<e_<=180 and -90<=s_<n_<=90
        glob = w_<=-170 and e_>=170 and s_<=-55 and n_>=70          # global or near-global: no check
        # a few Indian Ocean Meteosat records carry a mirrored longitude range in the catalogue: no check for them
        mirrored = bool(re.search(r'IODC|Indian Ocean|GSA-57|GSA-63', c['id']+' '+c.get('title',''))) and (w_+e_)/2 < 0
        if valid and not glob and not mirrored: C[-1]["bb"]=[round(x,1) for x in bb]
    m=META.get(c['id'],{})
    if m.get('res_m'):
        C[-1]["r"]=m['res_m']; C[-1]["rs"]=m['res_src']
        if m['res_src'].startswith('WMO') or 'finest of several' in m['res_txt']: C[-1]["rb"]=1
        C[-1]["rt"]=_short(m['snip'] if m['res_src'].startswith('catalogue') else m['res_txt'])
    if m.get('revisit'): C[-1]["rv"]=_short(m['revisit'],170)
S=[{"n":s['service'],"d":s['domain'],"a":s['area'],"x":s['description'],"m":s.get('markets',[]),"w":s.get('wiki_url'),
    "b":s.get('bok_service') or s.get('bok_area')} for s in tax['thematic_services']]
L={}
for r in links:
    first=r['path'].split(' | ')[0]
    ch=r['channel'][0] if ' + ' not in r['channel'] else ('A' if '→' in first else 'B' if re.match(r'^[A-Za-z0-9+\- ]{2,20}: ',first) and 'B detection' in r['channel'] else 'C')
    L.setdefault(r['earsc_service'],[]).append([cidx[r['collection_id']],r['link_type'][0],r['confidence'][0],r['path'],ch])
# ---- processing guidance: every entry has a URL that was seen in a web search on 2026-10-02
G={
 "solar":{"services":["Map & monitor solar energy (solar farms)","Forecasting sunlight exposure"],"items":[
   {"k":"service","t":"CAMS McClear clear-sky irradiation service (SoDa portal)","u":"https://www.soda-pro.com/web-services/radiation/cams-mcclear","note":"Time series at a point, no processing needed.","col":"infra"},
   {"k":"service","t":"CAMS gridded solar radiation (Atmosphere Data Store)","u":"https://ads.atmosphere.copernicus.eu/datasets/cams-gridded-solar-radiation","note":"","col":"data"},
   {"k":"reference","t":"Qu, Z. et al. (2017). Fast radiative transfer parameterisation for assessing the surface solar irradiance: the Heliosat-4 method. Meteorologische Zeitschrift 26(1), 33–57.","u":"https://doi.org/10.1127/metz/2016/0781","note":"Method behind the CAMS radiation service."}]},
 "flood":{"services":["Map and assess flooding"],"items":[
   {"k":"service","t":"Copernicus EMS Global Flood Monitoring (GFM) portal","u":"https://portal.gfm.eodc.eu/","note":"Flood extent already derived from every Sentinel-1 acquisition.","col":"data"},
   {"k":"service","t":"GFM product definition document","u":"https://extwiki.eodc.eu/GFM/PDD","note":""},
   {"k":"toolbox","t":"UN-SPIDER recommended practice: flood mapping and damage assessment with Sentinel-1 in Google Earth Engine","u":"https://www.un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping","note":"Step-by-step workflow with code."},
   {"k":"toolbox","t":"UN-SPIDER recommended practice: radar-based flood mapping with ESA SNAP","u":"https://www.un-spider.org/advisory-support/recommended-practices/recommended-practice-radar-based-flood-mapping","note":"Desktop workflow, threshold method."},
   {"k":"reference","t":"Salamon, P. et al. (2021). The new, systematic global flood monitoring product of the Copernicus Emergency Management Service. IEEE IGARSS 2021, 1053–1056.","u":"https://elib.dlr.de/144315","note":""}]},
 "air":{"services":["Monitor and forecast air quality & emissions (fluxes)","Monitor atmosphere composition"],"items":[
   {"k":"service","t":"Copernicus Atmosphere Data Store (CAMS forecasts and reanalyses)","u":"https://ads.atmosphere.copernicus.eu/","note":"","col":"infra"},
   {"k":"toolbox","t":"ESA Atmospheric Toolbox (CODA, HARP, VISAN, QDOAS)","u":"https://atmospherictoolbox.org/","note":"Reads Sentinel-5P, GOME-2 and CAMS data."},
   {"k":"toolbox","t":"HARP: turn Sentinel-5P level 2 files into gridded maps","u":"https://atmospherictoolbox.org/harp/","note":""},
   {"k":"toolbox","t":"ESA RUS tutorial: air quality monitoring with Sentinel-5P","u":"https://eo4society.esa.int/wp-content/uploads/2022/01/ATMO01_AirQuality_Monitoring.pdf","note":"Worked example for tropospheric NO2."}]},
 "ground":{"services":["Detect and monitor ground movement","Asset infrastructure monitoring","Measure and detect land surface change"],"items":[
   {"k":"service","t":"European Ground Motion Service (EGMS), Copernicus Land Monitoring Service","u":"https://egms.land.copernicus.eu/","note":"Ground displacement over Europe, already derived from Sentinel-1 by radar interferometry; viewed and downloaded in the EGMS Explorer.","col":"data"},
   {"k":"reference","t":"Crosetto, M. et al. (2023). Advanced analysis tools for the European Ground Motion Service data. ISPRS Archives XLVIII-1/W2-2023, 1229–1234.","u":"https://doi.org/10.5194/isprs-archives-XLVIII-1-W2-2023-1229-2023","note":""}]},
 "landcover":{"services":["Monitor land cover and detect change assessment","Monitor land use and land use change"],"items":[
   {"k":"service","t":"ESA WorldCover 10 m 2021 v200 (global land cover, 11 classes)","u":"https://doi.org/10.5281/zenodo.7254221","note":"From Sentinel-1 and Sentinel-2. The 2020 and 2021 maps were made with different algorithm versions: compare them with caution.","col":"data"}]},
 "fire":{"services":["Detect and monitor wildfires"],"items":[
   {"k":"service","t":"EFFIS current situation viewer (Copernicus Emergency Management Service)","u":"https://forest-fire.emergency.copernicus.eu/apps/effis_current_situation/index.html","note":"Active fires, burnt areas and fire danger for Europe and the Mediterranean, in near real time.","col":"infra"},
   {"k":"toolbox","t":"UN-SPIDER recommended practice: burn severity mapping (Sentinel-2 or Landsat 8, dNBR)","u":"https://un-spider.org/advisory-support/recommended-practices/recommended-practice-burn-severity","note":"Available for QGIS, R, Python and Google Earth Engine."},
   {"k":"toolbox","t":"UN-SPIDER burn-severity code repository","u":"https://github.com/UN-SPIDER/burn-severity","note":""}]},
 "urban":{"services":["Monitor urban green & blue areas","Monitor urban areas"],"items":[
   {"k":"service","t":"Copernicus Urban Atlas, Street Tree Layer 2018","u":"https://land.copernicus.eu/en/products/urban-atlas/street-tree-layer-stl-2018","note":"Ready-made tree cover for European functional urban areas; not in the DestinE Data Lake.","col":"data"},
   {"k":"service","t":"ESA WorldCover 10 m 2021 v200 (global land cover with a tree cover class)","u":"https://doi.org/10.5281/zenodo.7254221","note":"From Sentinel-1 and Sentinel-2; not in the DestinE Data Lake.","col":"data"},
   {"k":"toolbox","t":"UMEP for processing (QGIS plugin: Urban Multi-scale Environmental Predictor)","u":"https://plugins.qgis.org/plugins/author/Fredrik%20Lindberg,%20Nils%20Wallenberg","note":"Urban climate modelling from surface models and land cover."}]}}
GS={}
for g in G.values():
    for s in g['services']:
        assert any(x['n']==s for x in S), s
        GS[s]=g['items']
P=json.load(open('pilots_v2.json',encoding='utf-8'))
SV={}
for r in csv.DictReader(open(APP+'/taxonomy/variable_to_service.csv',encoding='utf-8'),delimiter=';'):
    if r['earsc_service']: SV.setdefault(r['earsc_service'],[]).append(r['oscar_variable'])
SNAP=[["DestinE Data Lake catalogue", open('hda_cols_fetched.txt').read().strip()],["EARSC taxonomy","2 October 2026"],["WMO OSCAR ratings","2 October 2026"],
      ["e-shape catalogue records","1 October 2026"],["e-shape Data Management Plans","file of 2 October 2026"]]
VR={}   # role of each variable for each service (product / input)
for r in csv.DictReader(open(APP+'/taxonomy/variable_to_service.csv',encoding='utf-8'),delimiter=';'):
    if r['earsc_service']: VR.setdefault(r['earsc_service'],{})[r['oscar_variable']]=r['role'][0]
import sys; sys.path.insert(0,APP)
import ei_proto
PRD={"items":[{"key":k,"title":r["title"],"res_m":r["res_m"],"lake":r["lake"],"outline":r["outline"],"gaps":r["gaps"],"vars":r["vars"],"svcs":r["svcs"],"rx":r["rx"],"not":r.get("not","")} for k,r in ei_proto.RECIPES.items()]}
data={"built":str(datetime.date.today()),"snap":SNAP,"PR":PRD,"S":S,"C":C,"L":L,"G":GS,"P":P,"T":T,"SV":SV,"VR":VR,
      "finder":"https://claude.ai/artifact/39mtYyB2kRNgsvDVeAaJfh","psnap":"catalogue: 1 October 2026; Data Management Plans: compiled file provided on 2 October 2026"}
js=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
mp='{"land":'+open('land.json').read()+',"rivers":'+open('bm_rivers.json').read()+',"lakes":'+open('bm_lakes.json').read()+',"urban":'+open('bm_urban.json').read()+',"roads":'+open('bm_roads.json').read()+',"borders":'+open('borders.json').read()+',"cities":'+open('cities.json',encoding='utf-8').read().replace('</','<\\/')+'}'
html=open(os.path.join(HERE,'page.html'),encoding='utf-8').read().replace('/*__DATA__*/null',js).replace('/*__MAP__*/null',mp)
open(OUT,'w',encoding='utf-8').write(html)
print(len(html),'bytes;',len(S),'services',len(C),'collections',sum(len(v) for v in L.values()),'links; guided services',len(GS),'; pilots',len(P))
