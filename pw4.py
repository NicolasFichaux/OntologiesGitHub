import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
MOCK = """
window.claude = { use: async (n) => {
  if (n==='sample'){ const s = async()=>({text:''}); s.json = async (p)=>{
     if (/e-shape pilot services/.test(p)) return {overall:'Two pilots address flood mapping.',matches:[{code:'S6P5',fit:'strong',why:'flood risk in urban areas',gaps:'check coverage'},{code:'S5P2',fit:'partial',why:'floodwater record',gaps:'Europe only'}]};
     return {understanding:'Map flood extent and check exposed critical infrastructure.',actor:'Civil protection agency',usage:'Prioritise interventions after a flood',
       candidates:[{service:'Map and assess flooding',confidence:0.9,reason:'flood extent'},{service:'Monitor critical infrastructure',confidence:0.6,reason:'exposed assets'}],
       questions:[],params:{place:'Ahr valley',bbox:[6.8,50.3,7.3,50.6],start:'2021-07-10',end:'2021-07-25',scale:'local',wants:'either'}}; }; return s; }
  if (n==='downloads') return { save: async()=>{} };
  return null; } };
"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','Flood extent in the Ahr valley and exposed infrastructure'); pg.click('#go'); pg.wait_for_selector('#pilots .svc'); pg.wait_for_timeout(900)
    print('nodes',pg.locator('.dv-node').count(),'out',pg.locator('.dv-node[data-where="out"]').count(),'gap',pg.locator('.dv-node[data-gap="1"]').count(),'decl edges',pg.locator('.dv-edge[data-c="decl"]').count())
    g=pg.locator('#divgraph'); g.scroll_into_view_if_needed(); pg.wait_for_timeout(300); g.screenshot(path=os.path.join(HERE,'out','div3.png'))
    pc=pg.locator('#pilots .svc').first; pc.scroll_into_view_if_needed(); pc.screenshot(path=os.path.join(HERE,'out','pilot3.png'))
    print([c.locator('h3').first.inner_text()[:40]+' | '+c.locator('.badge').first.inner_text() for c in pg.locator('#workshops .svc').all()])
    print('errors',errs[:5]); b.close()
