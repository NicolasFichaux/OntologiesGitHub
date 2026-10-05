"""Writes the three hand-made link tables (proposals by Claude, NOT validated).

v2 (3 Oct 2026)
- variable_to_service.csv gets a `role` column:
    product = the variable IS the information the service delivers (a product of that variable is ready to use)
    input   = the variable is one ingredient: the service still needs processing or modelling
- match terms tightened after a review of every "ready-to-use" link produced by v1
- collection_rules.csv gets a plain-language `rationale`, shown to the user instead of a regular expression
"""
import json, csv, re
tax = json.load(open('taxonomy/earsc_taxonomy.json'))['thematic_services']
SV = {s['service']: s for s in tax}
A = {'airq': 'Monitor and forecast air quality & emissions (fluxes)', 'atmo': 'Monitor atmosphere composition', 'sun': 'Forecasting sunlight exposure',
     'solar': 'Map & monitor solar energy (solar farms)', 'wind_en': 'Map & monitor wind energy (wind farms)', 'hydro_en': 'Map & monitor hydroelectric energy',
     'carbon': 'Assess changes in the carbon balance', 'climate': 'Assess climate change risk & climate forcing', 'weather': 'Forecast weather',
     'volcano': 'Assess and monitor volcanic activity', 'flood': 'Map and assess flooding', 'landslide': 'Forecast and assess landslides', 'fire': 'Detect and monitor wildfires',
     'quake': 'Assess damage from earthquakes', 'disaster': 'Map disaster areas and multi hazard assessment', 'hurricane': 'Detect & monitor hurricanes and typhoons',
     'lc': 'Monitor land cover and detect change assessment', 'lu': 'Monitor land use and land use change', 'urban': 'Monitor urban areas', 'urban_gb': 'Monitor urban green & blue areas',
     'urban_sur': 'Monitor urban surroundings', 'build': 'Monitor construction & buildings', 'defor': 'Assess deforestation / forest degradation', 'forest': 'Assess, monitor & manage onitor forest resources',
     'forest_dmg': 'Assess forest damage due to storms or insects', 'forest_c': 'Monitor forest carbon content', 'coast_lc': 'Monitor coastal land cover', 'veg_enc': 'Monitor vegetation encroachment',
     'eco': 'Assess land ecosystems and biodiversity', 'yield': 'Monitor and forecast crop yields', 'crop_stress': 'Assess and monitor crop disease and stress', 'crop_water': 'Monitor water use on crops and horticulture',
     'crop_dmg': 'Assess crop damage due to storms', 'illegal_crop': 'Detect illegal or undesired crops', 'farm_env': 'Assess environmental impact of farming',
     'water': 'Assess and monitor water bodies', 'wetland': 'Assess & monitor wetlands', 'runoff': 'Assess ground water and run-off', 'snow': 'Monitor & assess snow cover', 'glacier': 'Detect changes in glaciers',
     'river_ice': 'Monitor ice on rivers and lakes', 'dem': 'Baseline mapping', 'los': 'Map line of sight visibility (land surface)', 'surf_change': 'Measure and detect land surface change',
     'ground': 'Detect and monitor ground movement', 'asset': 'Asset infrastructure monitoring', 'mining': 'Monitor mineral extraction', 'transport': 'Map & monitor transport networks',
     'coast_wq': 'Assess & monitor coastal water quality', 'ocean_q': 'Monitor ocean quality & productivity', 'habitat': 'Monitor marine habitats', 'fish': 'Map fish shoals', 'ill_fish': 'Detect & monitor illegal fishing',
     'oil': 'Detect & monitor oil slicks', 'sea_poll': 'Monitor pollution at sea', 'ice': 'Detect & monitor ice-risk at sea', 'waves': 'Forecast & monitor ocean winds and waves', 'big_waves': 'Forecast & map large waves',
     'currents': 'Forecast & monitor ocean currents and drift', 'sealevel': 'Monitor ocean level & surface', 'ships': 'Detect ships in critical areas', 'ship_mov': 'Monitor ship movements',
     'acid': 'Monitor ocean acidification', 'health': 'Forecasting epidemics and diseases', 'flares': 'Monitor oil rigs & flares', 'popul': 'Assess pressures on populations and monitor humanitarian movement',
     'bathy': 'Monitor water depth or charting', 'invasive': 'Monitor invasive species'}
for k, v in A.items(): assert v in SV, (k, v)
H, M, P, I = 'high', 'medium', 'product', 'input'

# ---------- 1) OSCAR variable -> EARSC services : (match_terms, [(service, confidence, role)])
gas = lambda t, *extra: (t, [('airq', H, P), ('atmo', H, P), *extra])
trace = lambda t: (t, [('atmo', M, P)])
V = {
 # atmosphere: composition
 'Aerosol Optical Depth': (r'aerosol optical (depth|thickness)|\bAOD\b', [('atmo', H, P), ('airq', M, I), ('sun', H, I), ('solar', M, I)]),
 'Aerosol column burden': (r'aerosol (column|burden|load)', [('atmo', H, P), ('airq', M, I)]),
 'Aerosol mass mixing ratio': (r'aerosol (mass|mixing)', [('atmo', H, P), ('airq', M, I)]),
 'Aerosol type': (r'aerosol typ', [('atmo', H, P), ('airq', M, I)]),
 'Aerosol effective radius': (r'aerosol[^.]{0,30}radius', [('atmo', M, P)]),
 'Aerosol volcanic ash': (r'volcanic ash', [('volcano', H, P), ('atmo', M, P)]),
 'Aerosol volcanic ash Total Column': (r'volcanic ash', [('volcano', H, P), ('atmo', M, P)]),
 'NO2': gas(r'\bNO2\b|nitrogen dioxide'), 'NO2 Total Column': gas(r'\bNO2\b|nitrogen dioxide'), 'NO': gas(r'nitric oxide|nitrogen monoxide'),
 'SO2': gas(r'\bSO2\b|sulphur dioxide|sulfur dioxide', ('volcano', M, I)), 'SO2 Total Column': gas(r'\bSO2\b|sulphur dioxide|sulfur dioxide', ('volcano', M, I)),
 'O3': gas(r'\bO3\b|ozone'), 'O3 Total Column': gas(r'\bO3\b|ozone'), 'CO': gas(r'carbon monoxide'),
 'HCHO': gas(r'formaldehyde|HCHO'), 'HCHO Total Column': gas(r'formaldehyde|HCHO'),
 'CH4 mole fraction': gas(r'methane|\bCH4\b', ('carbon', M, I), ('climate', M, I), ('flares', M, I)),
 'CO2 mole fraction': gas(r'carbon dioxide|\bCO2\b', ('carbon', M, I), ('climate', M, I)),
 'N2O mole fraction': (r'nitrous oxide|\bN2O\b', [('atmo', H, P), ('climate', M, I)]),
 **{k: trace(t) for k, t in {'BrO': r'\bBrO\b', 'ClO': r'\bClO\b', 'ClONO2': r'ClONO2', 'CFC-11': r'CFC', 'CFC-12': r'CFC', 'CH3Br': r'CH3Br', 'COS': r'\bCOS\b|carbonyl sulphide', 'HNO3': r'HNO3|nitric acid',
                             'N2O5': r'N2O5', 'PAN': r'peroxyacetyl', 'SF6': r'\bSF6\b', 'C2H2': r'C2H2', 'C2H6': r'C2H6', 'H2O': r'water vapou?r', 'PSC occurrence': r'polar stratospheric cloud'}.items()},
 # atmosphere: weather. EARSC "Forecast weather" covers the monitoring of current conditions, so observed fields are products of it
 'Atmospheric temperature': (r'temperature profile|atmospheric temperature|temperature sounding|temperature and humidity', [('weather', H, P)]),
 'Specific humidity': (r'humidity', [('weather', H, P)]),
 'Integrated Water Vapour (IWV)': (r'water vapou?r|precipitable water', [('weather', H, P)]),
 'Wind (horizontal)': (r'atmospheric motion vector|\bAMV\b|wind profile|upper[- ]air wind', [('weather', H, P), ('hurricane', M, I)]),
 'Accumulated precipitation': (r'precipitation|rainfall|rain rate', [('weather', H, P), ('runoff', M, I), ('flood', M, I)]),
 'Precipitation intensity at surface (liquid or solid)': (r'precipitation|rainfall|rain rate', [('weather', H, P), ('flood', M, I), ('hurricane', M, I)]),
 'Cloud cover': (r'cloud (mask|cover|fraction|analysis)', [('weather', H, P), ('sun', H, I), ('solar', M, I)]),
 'Cloud type': (r'cloud (type|analysis)', [('weather', H, P)]),
 'Cloud top height': (r'cloud top', [('weather', M, P)]),
 'Cloud top temperature': (r'cloud top', [('weather', M, P), ('hurricane', M, I)]),
 'Cloud optical depth': (r'cloud optical|cloud properties', [('weather', M, I), ('sun', H, I)]),
 'Cloud drop effective radius': (r'effective radius|cloud properties', [('weather', M, I)]),
 'Cloud ice effective radius': (r'effective radius|cloud properties', [('weather', M, I)]),
 'Cloud ice': (r'cloud ice', [('weather', M, I)]), 'Cloud ice Total Column': (r'ice water path|cloud ice', [('weather', M, I)]),
 'Cloud liquid water (CLW)': (r'cloud liquid water|liquid water', [('weather', M, I)]),
 'Cloud liquid water (CLW) total column': (r'liquid water path|cloud liquid water', [('weather', M, I)]),
 'Height of the top of PBL': (r'boundary layer', [('weather', M, I)]),
 'Height of the tropopause': (r'tropopause', [('weather', M, I)]), 'Temperature of the tropopause': (r'tropopause', [('weather', M, I)]),
 'Freezing level height in clouds': (r'freezing level', [('weather', M, I)]), 'Melting layer depth in clouds': (r'melting layer', [('weather', M, I)]),
 'Total lightning stroke density': (r'lightning', [('weather', H, P)]),
 # radiation
 'Downward short-wave irradiance at Earth surface': (r'surface solar (irradiance|radiation)|solar surface (irradiance|radiation)|surface (incoming|downward|downwelling) (solar|short-?wave)|downward (surface )?short-?wave|\bDSSF\b|global horizontal|solar irradiance at (the )?surface',
                                                     [('solar', H, P), ('sun', H, P), ('climate', M, I)]),
 'Photosynthetically Active Radiation (PAR)': (r'(?<!absorbed )photosynthetically (active|available) radiation|\bPAR\b', [('yield', M, I), ('ocean_q', M, I)]),
 'Downward long-wave irradiance at Earth surface': (r'downward (surface )?long-?wave|downwelling long-?wave|\bDSLF\b', [('climate', M, I)]),
 'Upward long-wave irradiance at Earth surface': (r'upward (surface )?long-?wave|surface (emitted|upwelling) long-?wave', [('climate', M, I)]),
 'Upward long-wave irradiance at TOA': (r'outgoing long-?wave|\bOLR\b|outgoing LW|LW radiation at TOA', [('climate', M, I)]),
 'Upward short-wave irradiance at TOA': (r'reflected solar|outgoing short-?wave|SW radiation at TOA', [('climate', M, I)]),
 'Earth surface albedo': (r'albedo', [('climate', M, I)]),
 # land
 'Land cover': (r'land cover', [('lc', H, P), ('lu', H, P), ('coast_lc', M, P), ('urban', M, I), ('defor', M, I), ('health', M, I)]),
 'Fraction of vegetated land': (r'vegetation cover|fraction of (green )?vegetation|\bFVC\b|FCOVER', [('lc', H, I), ('urban_gb', M, I), ('veg_enc', M, I), ('defor', M, I)]),
 'Vegetation type': (r'vegetation type', [('eco', M, I), ('forest', M, I)]),
 'Leaf Area Index (LAI)': (r'leaf area index|\bLAI\b', [('yield', H, I), ('crop_stress', H, I), ('forest', M, I), ('eco', M, I)]),
 'Normalised Difference Vegetation Index (NDVI)': (r'\bNDVI\b|normali[sz]ed difference vegetation', [('yield', H, I), ('crop_stress', H, I), ('crop_water', M, P), ('veg_enc', M, I), ('urban_gb', M, I), ('eco', M, I), ('health', M, I)]),
 'Fraction of Absorbed PAR (FAPAR)': (r'\bFAPAR\b|\bFPAR\b|absorbed photosynthetically|\bOGVI\b|global vegetation index', [('yield', H, I), ('crop_stress', H, I), ('eco', M, I)]),
 'Biomass': (r'biomass', [('forest_c', H, P), ('forest', M, P), ('carbon', H, I)]),
 'Soil moisture at surface': (r'soil moisture|soil water', [('crop_water', H, P), ('runoff', H, P), ('yield', M, I), ('flood', M, I), ('landslide', M, I)]),
 'Soil moisture (in the roots region)': (r'root zone|soil water index|soil moisture', [('crop_water', H, P), ('runoff', M, P), ('yield', M, I)]),
 'Land surface temperature': (r'land surface temperature|\bLST\b', [('urban', M, I), ('urban_gb', M, I), ('crop_stress', M, I), ('crop_water', M, I)]),
 'Land surface topography': (r'digital elevation|elevation model|\bDEM\b|terrain (height|elevation)|land (surface )?topography', [('dem', H, P), ('los', H, I), ('surf_change', M, I)]),
 'Snow cover': (r'snow', [('snow', H, P), ('runoff', M, I)]), 'Snow status (wet/dry)': (r'snow', [('snow', H, P)]),
 'Snow water equivalent': (r'snow water', [('snow', H, P), ('runoff', M, I), ('hydro_en', M, I)]),
 'Glacier cover': (r'glacier', [('glacier', H, P)]), 'Glacier motion': (r'glacier', [('glacier', H, P)]), 'Glacier topography': (r'glacier', [('glacier', H, P)]),
 'Ice sheet topography': (r'ice sheet', [('glacier', M, P)]),
 'Fire fractional cover': (r'burn(t|ed) area|fire (extent|cover|scar)|active fire', [('fire', H, P)]),
 'Fire radiative power': (r'fire radiative|\bFRP\b', [('fire', H, P), ('airq', M, I)]),
 'Fire temperature': (r'active fire|fire temperature|fire (detection|monitoring)', [('fire', H, P)]),
 # ocean
 'Sea surface temperature': (r'sea surface temperature|\bSST\b', [('ocean_q', H, P), ('sealevel', M, P), ('habitat', M, P), ('fish', M, I), ('hurricane', M, I), ('climate', M, I)]),
 'Ocean chlorophyll concentration': (r'chlorophyll|ocean colou?r', [('coast_wq', H, P), ('ocean_q', H, P), ('habitat', M, P), ('fish', M, I), ('water', M, I)]),
 'Colour Dissolved Organic Matter (CDOM)': (r'\bCDOM\b|dissolved organic|ocean colou?r', [('coast_wq', M, P), ('ocean_q', M, P)]),
 'Ocean suspended sediments concentration': (r'suspended (matter|sediment)|\bTSM\b|ocean colou?r', [('coast_wq', H, P), ('ocean_q', M, P), ('water', M, I)]),
 'Ocean Diffuse Attenuation Coefficient (DAC)': (r'attenuation|\bKd\b|ocean colou?r', [('coast_wq', M, P), ('ocean_q', M, P)]),
 'Oil spill cover': (r'oil spill|oil slick', [('oil', H, P), ('sea_poll', H, P)]),
 'Sea-ice concentration': (r'sea[- ]ice', [('ice', H, P)]), 'Sea-ice type': (r'sea[- ]ice', [('ice', H, P)]), 'Sea-ice thickness': (r'sea[- ]ice', [('ice', H, P)]),
 'Sea-ice freeboard': (r'sea[- ]ice|freeboard', [('ice', M, P)]),
 'Significant wave height': (r'wave height|\bSWH\b', [('waves', H, P), ('big_waves', M, I), ('hurricane', M, I)]),
 'Dominant wave direction': (r'\bwaves?\b', [('waves', H, P)]), 'Dominant wave period': (r'\bwaves?\b', [('waves', H, P)]),
 'Wave directional energy frequency spectrum': (r'wave spectr', [('waves', M, P)]),
 'Wind speed (near surface)': (r'wind speed|ocean (surface )?winds?|sea surface winds?|coastal winds?|winds? (and|at)\b', [('waves', H, P), ('wind_en', M, I), ('hurricane', M, I)]),
 'Wind vector (near surface)': (r'wind vector|ocean (surface )?winds?|sea surface winds?|coastal winds?|winds? (and|at)\b', [('waves', H, P), ('wind_en', M, I), ('hurricane', M, I), ('oil', M, I)]),
 'Ocean dynamic topography': (r'sea (surface|level) height|dynamic topography|sea level|altimetry', [('sealevel', H, P), ('currents', H, I)]),
 'Coastal sea level (tide)': (r'sea level|\btides?\b', [('sealevel', H, P), ('currents', M, P)]),
}
oscar = json.load(open('taxonomy/oscar_extract.json'))
allv = sorted({r['variable'] for i in oscar['instruments'].values() for r in i['variables']})
unm = [v for v in allv if v not in V]; bad = [v for v in V if v not in allv]; assert not bad, bad
with open('taxonomy/variable_to_service.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['oscar_variable', 'match_terms', 'earsc_service', 'confidence', 'role', 'evidence', 'validated'])
    n = e = p = 0
    for v, (terms, links) in V.items():
        for a, c, role in links:
            ev = 'term found in EARSC description' if re.search(terms, SV[A[a]]['description'], re.I) else 'expert judgement (Claude)'
            n += 1; e += ev.startswith('term'); p += role == P; w.writerow([v, terms, A[a], c, role, ev, 'no'])
    for v in unm: w.writerow([v, '', '', '', '', 'no EARSC service identified', 'no'])
print('variables mapped', len(V), '/', len(allv), '; links', n, '; product role', p, '; input role', n - p, '; with textual evidence', e)

# ---------- 2) instrument -> services by detection / interpretation (not physical variables); always needs processing
D = {'C-SAR': [('flood', H, 'SAR backscatter change, all-weather'), ('ships', H, 'bright targets on the sea surface'), ('ship_mov', M, 'needs fusion with AIS'), ('ill_fish', M, 'vessel detection without AIS'),
               ('ground', H, 'InSAR (SLC product)'), ('surf_change', H, 'InSAR / coherence (SLC)'), ('asset', M, 'InSAR on infrastructure (SLC)'), ('quake', M, 'InSAR / coherence change'),
               ('volcano', M, 'InSAR deformation'), ('landslide', M, 'InSAR, coherence'), ('defor', M, 'backscatter time series'), ('disaster', M, 'rapid mapping'), ('river_ice', M, 'backscatter'), ('wetland', M, 'backscatter time series')],
     'MSI': [('urban', H, '10 m multispectral imagery'), ('urban_gb', H, 'vegetation and water indices at 10 m'), ('urban_sur', M, 'sprawl mapping'), ('build', M, '10 m: large structures only'),
             ('defor', H, 'time series'), ('forest_dmg', M, 'change detection'), ('fire', H, 'burnt area, active fire in SWIR'), ('flood', M, 'cloud-limited'), ('water', H, 'water extent and quality'),
             ('wetland', M, 'indices'), ('crop_dmg', M, 'change detection'), ('illegal_crop', M, 'crop classification'), ('mining', M, 'change detection'), ('coast_wq', M, 'turbidity near shore'),
             ('disaster', M, 'cloud-limited'), ('glacier', M, 'outlines'), ('bathy', M, 'satellite-derived bathymetry, clear shallow water'), ('invasive', M, 'sargassum detection')],
     **{k: [('lu', H, 'long time series of 30 m imagery'), ('lc', H, '30 m multispectral imagery'), ('defor', H, 'long time series'), ('urban', M, '30 m imagery'), ('urban_sur', M, 'sprawl over decades'),
            ('water', H, 'water extent'), ('glacier', M, 'outlines'), ('fire', M, 'burnt area'), ('mining', M, 'change detection')] for k in ('TM', 'ETM+', 'OLI', 'MSS')},
     'TIRS': [('urban', M, 'surface temperature at 100 m (heat islands)'), ('urban_gb', M, 'surface temperature'), ('crop_water', M, 'evapotranspiration')],
     'SEVIRI': [('hurricane', H, 'geostationary imagery every 15 min')], 'FCI': [('hurricane', H, 'geostationary imagery every 10 min')], 'MVIRI': [('hurricane', M, 'geostationary imagery')],
     'AVHRR': [('hurricane', M, 'polar imagery')], 'OLCI': [('invasive', M, 'floating algae indices'), ('water', M, 'inland water quality, 300 m')],
     'SRAL': [('water', M, 'inland water level by altimetry'), ('hydro_en', M, 'reservoir level')], 'Poseidon-4': [('water', M, 'inland water level by altimetry')]}
with open('taxonomy/instrument_to_service.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['hda_instrument', 'earsc_service', 'confidence', 'rationale', 'only_if_id_matches', 'validated'])
    for i, l in D.items():
        for a, c, r in l: w.writerow([i, A[a], c, r, 'SLC' if 'InSAR' in r else '', 'no'])

# ---------- 3) product families (collections that declare no instrument): regex on the collection id + plain-language rationale
E_, D_ = 'enabling', 'direct'
R = [
 (r'ECMWF\.DAT\.CAMS_EUROPE_AIR_QUALITY', 'CAMS regional air-quality forecasts or reanalyses for Europe (modelled pollutant concentrations)', [('airq', D_, H), ('atmo', D_, H), ('health', E_, M)]),
 (r'CAMS_GLOBAL_ATMOSHERIC_COMPO|CAMS_GLOBAL_REANALYSIS_EAC4', 'CAMS global atmospheric composition: aerosols and reactive gases, forecast or reanalysis', [('atmo', D_, H), ('airq', D_, M), ('health', E_, M)]),
 (r'CAMS_GLOBAL_EMISSION_INVENTORIES', 'gridded inventories of anthropogenic and natural emissions', [('airq', D_, H)]),
 (r'CAMS_GLOBAL_FIRE_EMISSIONS', 'biomass-burning emissions derived from satellite fire radiative power (GFAS)', [('fire', D_, H), ('airq', D_, M)]),
 (r'ECMWF\.DAT\.(CAMS_GLOBAL_GREENHOUSE_GAS|CAMS_GREENHOUSE_GAS_FLUXES|CO2_DATA|METHANE_DATA)', 'greenhouse-gas concentrations or fluxes (CAMS reanalysis, inversions or satellite retrievals)', [('atmo', D_, H), ('airq', D_, H), ('carbon', E_, M), ('climate', E_, M)]),
 (r'CAMS_GLOBAL_RADIATIVE_FORCING', 'radiative forcing estimates for greenhouse gases, ozone and aerosols', [('climate', D_, H)]),
 (r'CAMS_SOLAR_RADIATION', 'CAMS solar radiation time series at a point: global, direct and diffuse irradiation, clear sky and all sky', [('solar', D_, H), ('sun', D_, H)]),
 (r'SARAH', 'SARAH climate data record of surface solar radiation from Meteosat', [('solar', D_, H), ('sun', D_, H), ('climate', E_, M)]),
 (r'CEMS_FIRE|WILDFIRE_FWI', 'fire danger indices (Fire Weather Index): fire risk, not observed fires', [('fire', D_, H)]),
 (r'LSA-FRM', 'fire risk map merging weather forecasts and satellite fire observations: fire risk, not observed fires', [('fire', D_, H)]),
 (r'GLOFAS|EFAS', 'modelled river discharge and flood forecasts (early warning), not an observed flood extent', [('flood', D_, H), ('runoff', D_, H), ('hydro_en', E_, M)]),
 (r'HYDROLAND', 'land-surface hydrology simulations (soil moisture, runoff, discharge) driven by the Climate digital twin', [('runoff', D_, H), ('flood', E_, M), ('crop_water', E_, M)]),
 (r'HYDROMET_EXTREMES', 'catalogue of extreme precipitation events', [('flood', E_, M), ('disaster', E_, M), ('climate', E_, M)]),
 (r'CMIP6|DT_CLIMATE|ISIMIP\.DAT\.CLIMATE|SIS_HYDROLOGY', 'climate projections or scenario simulations', [('climate', D_, H)]),
 (r'ISIMIP\.DAT\.SOCIO', 'socio-economic input data for climate-impact models', [('climate', E_, M)]),
 (r'DT_EXTREMES', 'kilometre-scale forecasts of weather extremes (Extremes digital twin)', [('weather', D_, H), ('hurricane', E_, M), ('flood', E_, M), ('disaster', E_, M)]),
 (r'ENERGY_INDICATORS', 'wind and solar energy indicators computed from Climate digital twin simulations', [('wind_en', D_, M), ('solar', D_, M), ('climate', E_, M)]),
 (r'ERA5|UERRA', 'atmospheric reanalysis: hourly history of weather variables over decades', [('weather', D_, M), ('climate', E_, H), ('wind_en', E_, M), ('solar', E_, M), ('yield', E_, M)]),
 (r'ERA5_LAND', 'land reanalysis: soil moisture, runoff, snow and surface temperature', [('runoff', E_, M), ('crop_water', E_, M)]),
 (r'SEASONAL_FORECAST', 'seasonal forecasts, several months ahead', [('weather', D_, M), ('yield', E_, M), ('hydro_en', E_, M)]),
 (r'GLACIER', 'glacier inventory or glacier mass change', [('glacier', D_, H)]),
 (r'SATELLITE_SEA_ICE|SEAICE_GLO', 'sea-ice concentration, edge, type, thickness or drift', [('ice', D_, H)]),
 (r'SEA_LEVEL_DAILY|SEALEVEL_GLO', 'gridded sea level from satellite altimetry', [('sealevel', D_, H), ('currents', E_, M)]),
 (r'UTH-CM|MHSMWHS|GIRAFE', 'climate data record of humidity or precipitation', [('climate', E_, M)]),
 (r'GOMPMA', 'climate data record of aerosol optical properties', [('atmo', D_, M), ('climate', E_, M)]),
 (r'IAGOS', 'in-situ atmospheric composition measured from commercial aircraft', [('atmo', D_, M)]),
 (r'GSW\.', 'Global Surface Water: where and when surface water was present, from Landsat', [('water', D_, H), ('wetland', E_, M), ('flood', E_, M)]),
 (r'COP-DEM', 'Copernicus digital elevation model', [('dem', D_, H), ('los', E_, H), ('flood', E_, M), ('landslide', E_, M)]),
 (r'CORINE', 'CORINE Land Cover inventory for Europe', [('lc', D_, H), ('lu', D_, H), ('coast_lc', D_, M), ('urban_sur', E_, M)]),
 (r'LULC', 'labelled image patches for training land-cover classifiers (not a map)', [('lc', E_, M)]),
 (r'CLMS\.DAT\.GLO\.(NDVI|LAI|FAPAR|FCOVER)', 'global vegetation index product, every 10 days', [('yield', E_, H), ('crop_stress', E_, H), ('eco', E_, M), ('forest', E_, M)]),
 (r'DMP300', 'dry matter productivity: vegetation growth rate', [('yield', D_, M), ('carbon', E_, M)]),
 (r'HRVPP', 'high-resolution vegetation phenology and productivity from Sentinel-2', [('yield', E_, H), ('crop_stress', E_, M), ('eco', E_, M), ('forest', E_, M)]),
 (r'GHSL\.DAT\.(BUILT|ESM|SMOD|DUC|FUA|UCDB|LAND)', 'Global Human Settlement Layer: built-up areas, settlement types or urban centres', [('urban', D_, H), ('urban_sur', D_, M), ('lu', E_, M)]),
 (r'GHSL\.DAT\.BUILT', 'built-up surface, height or volume grids', [('build', D_, H)]),
 (r'GHSL\.DAT\.(POP|ENACT)|EUSTAT\.DAT\.POP', 'population grids or regional population statistics', [('popul', E_, M), ('urban', E_, M)]),
 (r'SOIL_SEALING', 'soil sealing statistics by region (Eurostat)', [('lu', D_, M), ('urban', E_, M)]),
 (r'GREENHOUSE_GAS_EMISSION_AGRICULTURE', 'statistics on greenhouse-gas emissions from agriculture (Eurostat)', [('farm_env', D_, M)]),
 (r'PROTECTED_AREAS|GBIF', 'biodiversity records or protected-area statistics', [('eco', E_, M)]),
 (r'SPACENET.*BUILD|ALL_WEATHER_MAPPING', 'labelled very-high-resolution images of a few cities, for training building detectors', [('build', E_, M)]),
 (r'SPACENET.*ROADS', 'labelled images of a few cities, for training road extraction', [('transport', E_, M)]),
 (r'MO\.DAT\.GLOBAL_(ANALYSISFORECAST|MULTIYEAR)_PHY', 'ocean physics model: currents, temperature, salinity, sea level', [('currents', D_, H), ('sealevel', D_, M), ('oil', E_, M), ('invasive', E_, M)]),
 (r'MULTIOBS_GLO_PHY_(MYNRT|TSUV|UVW)|INSITU_GLO_PHY_UV', 'ocean currents derived from observations', [('currents', D_, H), ('oil', E_, M)]),
 (r'INSITU_GLO_PHY_TS_OA|MULTIOBS_GLO_PHY_S_SURFACE', 'gridded ocean temperature and salinity from observations', [('sealevel', D_, M), ('currents', E_, M)]),
 (r'MO\.DAT\.GLOBAL_(ANALYSISFORECAST|MULTIYEAR)_WAV|WAVE_GLO', 'ocean waves: model or satellite observations', [('waves', D_, H), ('big_waves', E_, M)]),
 (r'GLOBAL_ANALYSISFORECAST_BGC|OCEANCOLOUR|MULTIOBS_GLO_BIO_BGC', 'ocean biogeochemistry and ocean colour: chlorophyll, plankton', [('ocean_q', D_, H), ('habitat', E_, M), ('fish', E_, M), ('coast_wq', E_, M)]),
 (r'GLOBAL_MULTIYEAR_BGC', 'modelled biomass of low and mid trophic levels (zooplankton, micronekton)', [('habitat', D_, M), ('fish', E_, M), ('ocean_q', E_, M)]),
 (r'NUTRIENTS_CARBON|CARBON_SURFACE', 'ocean carbon and nutrient fields', [('acid', D_, H)]),
 (r'MO\.DAT\.SST_GLO', 'sea surface temperature analyses', [('ocean_q', D_, M), ('sealevel', D_, M), ('habitat', D_, M), ('fish', E_, M), ('climate', E_, M)]),
 (r'MO\.DAT\.WIND_GLO', 'sea surface wind from scatterometers', [('waves', D_, H), ('wind_en', E_, M)]),
]
with open('taxonomy/collection_rules.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['collection_id_regex', 'rationale', 'earsc_service', 'link_type', 'confidence', 'validated'])
    for rx, why, l in R:
        re.compile(rx)
        for a, t, c in l: w.writerow([rx, why, A[a], t, c, 'no'])
print('detection links', sum(len(l) for l in D.values()), '; family rules', len(R), '; family links', sum(len(l) for _, _, l in R))
