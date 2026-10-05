"""Rebuilds data/pilots_v2.json from the e-shape catalogue snapshot and the Data Management Plans.
Run: python pilots_build.py"""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APP=os.path.join(HERE,'..','local_app'); DATA=os.path.join(HERE,'data')
OUT=os.environ.get('NAV_OUT', os.path.join(HERE,'dist','earth-data-navigator.html'))
os.makedirs(os.path.dirname(OUT), exist_ok=True); os.chdir(DATA)
import json, re, collections
old={p['code']:p for p in json.load(open('eshape_P.json',encoding='utf-8'))}
dmp=json.load(open('dmp_new.json',encoding='utf-8'))
tax={s['service'] for s in json.load(open(APP+'/taxonomy/earsc_taxonomy.json'))['thematic_services']}
cols=json.load(open('hda_cols.json'))
INFO={  # pilot -> EARSC services (assigned by hand from the pilot titles and abstracts; proposals)
"S1P1":["Monitor and forecast crop yields","Food security monitoring"],"S1P2":["Assess environmental impact of farming","Monitor and forecast crop yields"],
"S1P3":["Assess and monitor crop disease and stress","Monitor and forecast crop yields"],"S1P4":["Monitor water use on crops and horticulture","Monitor and forecast crop yields"],
"S1P5":["Assess and monitor crop disease and stress","Monitor water use on crops and horticulture"],"S1P6":["Monitor land use and land use change","Assess environmental impact of farming"],
"S1P7":["Monitor and forecast crop yields","Assess and monitor crop disease and stress"],"S2P1":["Monitor atmosphere composition","Monitor and forecast air quality & emissions (fluxes)"],
"S2P2":["Monitor atmosphere composition"],"S2P3":["Monitor and forecast air quality & emissions (fluxes)","Forecasting epidemics and diseases"],"S2P4":["Forecasting epidemics and diseases"],
"S3P1":["Map & monitor solar energy (solar farms)","Forecasting sunlight exposure"],"S3P2":["Map & monitor solar energy (solar farms)","Monitor urban areas"],
"S3P3":["Map & monitor wind energy (wind farms)","Forecast & monitor ocean winds and waves"],"S3P4":["Map & monitor wind energy (wind farms)"],
"S4P1":["Assess land ecosystems and biodiversity"],"S4P2":["Assess land ecosystems and biodiversity"],"S4P3":["Assess land ecosystems and biodiversity"],
"S5P1":["Assess ground water and run-off","Assess and monitor water bodies"],"S5P2":["Map and assess flooding","Assess and monitor water bodies"],
"S5P3":["Assess & monitor coastal water quality"],"S5P4":["Monitor invasive species"],"S5P5":["Detect & monitor illegal fishing","Monitor ship movements"],
"S5P6":["Assess and monitor water bodies","Assess & monitor coastal water quality"],"S5P7":["Monitor ocean quality & productivity"],"S6P1":["Assess and monitor volcanic activity"],
"S6P2":["Forecast weather","Map and assess flooding"],"S6P3":["Detect and monitor ground movement","Asset infrastructure monitoring"],
"S6P4":["Assess crop damage due to storms","Map disaster areas and multi hazard assessment"],"S6P5":["Map and assess flooding"],
"S6P6":["Monitor & assess snow cover","Map disaster areas and multi hazard assessment"],"S7P1":["Assess changes in the carbon balance","Monitor and forecast air quality & emissions (fluxes)"],
"S7P2":["Forecast weather","Assess climate change risk & climate forcing"],"S7P3":["Assess, monitor & manage onitor forest resources","Forecast weather"],
"S7P4":["Monitor & assess snow cover","Map & monitor hydroelectric energy"],"S7P5":["Forecast weather","Assess climate change risk & climate forcing"],
"S7P6":["Monitor and forecast air quality & emissions (fluxes)"]}
for k,v in INFO.items():
    for s in v: assert s in tax,(k,s)
I=re.I
DATA_SRC=[  # label, regex, flags, Data Lake collection-id regex (None = not in the Data Lake)
("Sentinel-1 radar imagery",r"sentinel[- ]?1\b|\bS-1\b",I,r"SENTINEL-1"),("Sentinel-2 optical imagery",r"sentinel[- ]?2\b|\bS-2\b",I,r"SENTINEL-2"),
("Sentinel-3 (OLCI, SLSTR)",r"sentinel[- ]?3\b|\bOLCI\b|\bSLSTR\b",I,r"SENTINEL-3"),("Sentinel-5P (TROPOMI)",r"sentinel[- ]?5\s?p?\b|tropomi",I,r"SENTINEL-5P"),
("Landsat imagery",r"landsat",I,r"LANDSAT"),("Meteosat (SEVIRI)",r"\bSEVIRI\b|meteosat|\bMSG\b",I,r"\.MSG\.|\.MTG\."),
("CAMS atmosphere and radiation data",r"\bCAMS\b|copernicus atmosphere",I,r"CAMS_"),("C3S climate data (ERA5, seasonal forecasts)",r"\bC3S\b|copernicus climate|\bERA5\b|climate data store|\bCDS\b",I,r"ERA5|SEASONAL_FORECAST|CMIP6|SIS_"),
("Copernicus Marine data",r"\bCMEMS\b|copernicus marine",I,r"^EO\.MO\."),("Copernicus Land data",r"\bCLMS\b|copernicus land|corine",I,r"^EO\.CLMS"),
("Copernicus Emergency (EFAS, GloFAS)",r"\bEFAS\b|glofas|copernicus emergency",I,r"EFAS|GLOFAS|CEMS_"),("Digital elevation model",r"\bDEM\b|digital elevation|\bDSM\b|digital surface model",I,r"^EO\.DEM"),
("MODIS",r"\bMODIS\b",I,None),("VIIRS",r"\bVIIRS\b",I,None),("In situ measurements",r"in[- ]situ|ground[- ]based (measurement|station|sensor)|monitoring stations?|ground stations?",I,None),
("Vessel tracking (AIS, VMS)",r"\bAIS\b|\bVMS\b",0,None),("LiDAR",r"\blidar\b",I,None),("Numerical weather model output",r"\bWRF\b|\bNWP\b|numerical weather|\bIFS\b",0,None),
("Farm sensors (IoT)",r"\bIoT\b",0,None,"cat"),("Commercial very-high-resolution imagery",r"planetscope|pl[eé]iades|\bSPOT[- ]?[5-7]\b|worldview|very high resolution",I,None),
("Citizen observations",r"crowd[- ]?sourc|citizen science|citizen observ",I,None)]
INFRA=[("OGC WMS",r"\bWMS\b",0),("OGC WFS",r"\bWFS\b",0),("OGC WCS",r"\bWCS\b",0),("OGC WPS",r"\bWPS\b",0),("OGC CSW catalogue",r"\bCSW\b",0),
("REST API",r"\bREST\b|\bAPI\b",0),("NetCDF files",r"netcdf",I),("GeoTIFF files",r"geotiff",I),("THREDDS / OPeNDAP",r"thredds|opendap",I),
("Copernicus DIAS cloud",r"\bDIAS\b|creodias|\bmundi\b|wekeo|sobloo",I),("Copernicus Climate / Atmosphere Data Store",r"climate data store|\bCDS\b|atmosphere data store|\bADS\b",0),
("Zenodo repository",r"zenodo",I),("Git repository",r"github|gitlab|\bgit\b",I),("Jupyter notebook",r"jupyter|notebook",I),
("Web application or portal",r"web ?app\b|web application|web[- ]?portal|dashboard|web[- ]?service|webgis|online application",I),("Mobile application",r"mobile app",I),
("GEOSS / GEO DAB",r"\bGEOSS\b|geo dab|\bDAB\b",0),("DEIMS-SDR",r"DEIMS",0),("Google Earth Engine",r"earth engine",I)]
dl_count=lambda rx: sum(1 for c in cols if re.search(rx,c['id']))
LVN=["Discovery metadata","Online access","Standard encoding","Documentation","Traceability","Quality control","Preservation","Data verification","Reprocessing","Persistent identifiers"]
P=[]; stats=collections.Counter()
for code,o in old.items():
    d=dmp.get(code); dup = code=="S6P4"       # the S6P4 sheet is a copy of S1P2
    has = bool(d) and bool(d.get('received')) and not dup
    geo=[[g['p'],LVN[i] if i<10 else g['name'],(g['s2'] if g['s2'] is not None else g['s1'])] for i,g in enumerate(d['geo'])] if has else []
    dmptxt=' '.join([g['det']+' '+g['exc'] for g in d['geo']]+[f['det'] for f in d['fair']]) if has else ''
    cat=' '.join([o.get('abstract') or '',' '.join(o.get('kw') or []),' '.join(o.get('links') or [])])
    src=[]
    for lab,rx,fl,dlrx,*only in DATA_SRC:
        inD=bool(re.search(rx,dmptxt,fl)) and not only; inC=bool(re.search(rx,cat,fl))
        if inD or inC: src.append({"l":lab,"dl":dl_count(dlrx) if dlrx else 0,"from":"DMP" if inD and not inC else "catalogue" if inC and not inD else "DMP and catalogue"})
    inf=[lab for lab,rx,fl in INFRA if re.search(rx,dmptxt+' '+cat,fl)]
    adapt=[f"Demonstrated in: {', '.join(o['places'])}"] if o.get('places') else []
    if has:
        adapt+= [f"{LVN[i]} not started" for i,g in enumerate(d['geo'][:10]) if (g['s2'] if g['s2'] is not None else g['s1'])==1]
        if re.search(r"registration|log[- ]?in|credentials|user account",dmptxt,I): adapt.append("Registration required")
        if re.search(r"commercial|paid|subscription|fee",dmptxt,I): adapt.append("Commercial / paid model")
        n=sum(1 for g in d['geo'] if g['exc'] and not re.match(r"\s*(no|none|not applicable)\b",g['exc'],I))
        if n: adapt.append(f"{n} declared exception(s)")
    if dup: adapt.append("DMP sheet identical to S1P2 in the source file: to check")
    stats['dmp']+=has; stats['src']+=bool(src); stats['infra']+=bool(inf)
    P.append({"code":code,"title":o["title"],"showcase":o["showcase"],"org":o["org"],"places":o.get("places",[]),"hasDMP":has,"kw":o.get("kw",[]),
              "short":" ".join((o.get("short") or "").split()),"geo":geo,"comp":[],"stds":inf,"adapt":adapt,
              "contacts":[{k:c.get(k,"") for k in ("individual","organisation","email","position","src")} for c in o.get("contacts",[])],
              "uuids":o.get("uuids",[]),"info":INFO.get(code,[]),"data":src,"infra":inf,
              "snaps":o.get("snaps",[]),
              "dmp":{"version":d.get("version"),"geo":[{"p":g["p"],"name":LVN[i] if i<10 else g["name"],"s1":g["s1"],"s2":g["s2"],"det":g["det"],"exc":g["exc"],"why":g["why"]} for i,g in enumerate(d["geo"])],
                     "fair":d["fair"]} if has else None})
json.dump(P,open('pilots_v2.json','w',encoding='utf-8'),ensure_ascii=False)
print(dict(stats), 'of', len(P))
for c in ('S3P2','S5P2','S2P3','S6P5','S7P2'):
    p=next(x for x in P if x['code']==c); print(c,'| info',p['info'],'\n   data',[(s['l'],s['dl'],s['from']) for s in p['data']],'\n   infra',p['infra'],'\n   adapt',p['adapt'])
print('pilots with no data source detected:',[p['code'] for p in P if not p['data']]); print('no infra:',[p['code'] for p in P if not p['infra']])
print(collections.Counter(s['l'] for p in P for s in p['data']).most_common())
