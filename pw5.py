import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
MOCK = """
window.claude = { use: async (n) => {
  if (n==='sample'){ const s = async()=>({text:''}); s.json = async (p)=>{
     if (/e-shape pilot services/.test(p)) return {overall:'ok',matches:[{code:'S7P2',fit:'partial',why:'w',gaps:'g'}]};
     return {understanding:'Find districts of Marseille that overheat in summer.',actor:'City planning department',usage:'Decide where to plant trees first',
       candidates:[{service:'Monitor urban green & blue areas',confidence:0.86,reason:'tree cover and heat',information:'Tree canopy share per district',resolution:'district level, about 10 m',frequency:'once a year, in spring',delay:''},
                   {service:'Detect and monitor wildfires',confidence:0.5,reason:'test',information:'Burnt area around the city',resolution:'about 20 m',frequency:'after each fire',delay:'within days'}],
       questions:[],params:{place:'Marseille',bbox:[5.2,43.15,5.6,43.4],start:'2023-06-01',end:'2023-08-31',scale:'local',wants:'either'}}; }; return s; }
  if (n==='downloads') return { save: async(o)=>{ window.__saved=o; } };
  return null; } };
"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','Which districts of Marseille overheat?'); pg.click('#go'); pg.wait_for_selector('#pilots .svc'); pg.wait_for_timeout(800)
    print('tooCoarse:',pg.evaluate("[tooCoarse('SEVIRI → Cloud cover (OSCAR 1 – primary)'),tooCoarse('MSI: burnt area'),tooCoarse('id matches /CEMS_FIRE/'),localNeed()]"))
    print('coarse badges',pg.locator('.badge',has_text='too coarse').count())
    print('info nodes:',[n.get_attribute('aria-label') for n in pg.locator('.dv-node[data-kind="service"]').all()])
    print('ctxInfo:',repr(pg.input_value('#ctxInfo')))
    print('bands:',pg.locator('.band summary').all_inner_texts())
    g=pg.locator('#divgraph'); g.scroll_into_view_if_needed(); g.screenshot(path=os.path.join(HERE,'out','div4.png'))
    row=pg.locator('.layer').first; row.locator('button',has_text='How to get it').click(); pg.wait_for_timeout(800)
    row.locator('button',has_text='Save request for the local app').click(); pg.wait_for_timeout(200)
    print('saved:',pg.evaluate("window.__saved && window.__saved.filename"), pg.evaluate("window.__saved && window.__saved.data")[:260].replace('\n',' '))
    open(os.path.join(HERE,'out','req_example.json'),'w').write(pg.evaluate("window.__saved.data"))
    print('errors',errs[:5]); b.close()
