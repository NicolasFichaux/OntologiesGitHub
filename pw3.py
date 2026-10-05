import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
MOCK = """
window.__prompts=[];
window.claude = { use: async (n) => {
  if (n==='sample'){ const s = async()=>({text:''}); s.json = async (p)=>{ window.__prompts.push(p);
     if (/e-shape pilot services/.test(p)) return {overall:'One pilot is close.',matches:[{code:'S7P2',fit:'partial',why:'w',gaps:'g'}]};
     if (/reworded their context/.test(p)) return {understanding:'Rank districts for tree planting and check summer overheating.',actor:'Green spaces department, QGIS users',usage:'Rank districts for the tree-planting plan',
       candidates:[{service:'Monitor urban green & blue areas',confidence:0.9,reason:'tree cover'},{service:'Monitor land cover and detect change assessment',confidence:0.6,reason:'land cover'}],questions:[],
       params:{place:'Marseille',bbox:[5.2,43.15,5.6,43.4],start:'2023-06-01',end:'2023-08-31',scale:'local',wants:'either'}};
     return {understanding:'Find districts of Marseille with little tree cover that overheat in summer.',actor:'',usage:"Decide where to plant trees first",
       candidates:[{service:'Monitor urban green & blue areas',confidence:0.62,reason:'tree cover and heat',information:'Tree canopy share per district',resolution:'district level, about 10 m',frequency:'once a year',delay:''},{service:'Monitor urban areas',confidence:0.55,reason:'urban heat island'}],
       questions:[],params:{place:'Marseille',bbox:[5.2,43.15,5.6,43.4],start:'2023-06-01',end:'2023-08-31',scale:'local',wants:'either'}}; }; return s; }
  if (n==='downloads') return { save: async()=>{} };
  return null; } };
"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','Which districts of Marseille lack tree cover and overheat in summer?'); pg.click('#go'); pg.wait_for_selector('#workshops .svc'); pg.wait_for_timeout(900)
    cards=lambda: [c.locator('h3').first.inner_text()+' | '+c.locator('.badge').first.inner_text()+' | '+c.locator('p strong').first.locator('xpath=..').inner_text()[:70] for c in pg.locator('#workshops .svc').all()]
    print('\n'.join(cards())); print('eco/use:',repr(pg.input_value('#ctxEco')),'|',repr(pg.input_value('#ctxUse')))
    pg.click('#ctxGo'); print('no change ->',pg.inner_text('#divstatus'))
    pg.fill('#ctxEco','Green spaces department of the metropolitan area, we use QGIS'); pg.fill('#ctxUse','Rank districts for the tree-planting plan'); pg.click('#ctxGo'); pg.wait_for_timeout(1200)
    print('change:',pg.inner_text('#divchange')); print('ctx in prompt:', pg.evaluate("window.__prompts.filter(p=>/reworded their context/.test(p)&&/Green spaces department/.test(p)).length"))
    print('\n'.join(cards())); print('eco/use after:',repr(pg.input_value('#ctxEco')),'|',repr(pg.input_value('#ctxUse')))
    print('services in graph:',pg.locator('.dv-node[data-kind="service"]').count(),'| need node:',pg.locator('.dv-node[data-kind="need"]').first.get_attribute('aria-label'))
    el=pg.locator('#divedit'); el.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(HERE,'out','ws1.png'),clip=None,full_page=False)
    box=pg.locator('#workshops'); box.scroll_into_view_if_needed(); box.screenshot(path=os.path.join(HERE,'out','ws2.png'))
    g=pg.locator('#divgraph'); g.scroll_into_view_if_needed(); g.screenshot(path=os.path.join(HERE,'out','div4.png')); print('coarse badges',pg.locator('.badge',has_text='too coarse').count(),'| info node:',pg.locator('.dv-node[data-kind="service"]').first.get_attribute('aria-label'))
    pg.click('#reset'); pg.wait_for_timeout(100); print('after reset sdiv hidden',pg.locator('#sdiv').is_hidden(),'eco',repr(pg.input_value('#ctxEco')))
    print('ctxInfo:',repr(pg.input_value('#ctxInfo')))
    print('errors',errs[:5]); b.close()
