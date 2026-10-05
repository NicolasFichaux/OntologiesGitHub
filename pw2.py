import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
MOCK = """
window.claude = { use: async (n) => {
  if (n==='sample'){ const s = async()=>({text:''}); s.json = async (p)=>{
     if (/e-shape pilot services/.test(p)) return {overall:'One pilot is close.',matches:[{code:'S7P2',fit:'partial',why:'w',gaps:'g'},{code:'S3P2',fit:'weak',why:'w',gaps:'g'}]};
     return {understanding:'Find districts of Marseille with little tree cover that overheat in summer.',actor:'City planning department',usage:'Decide where to plant trees first',
       candidates:[{service:'Monitor urban green & blue areas',confidence:0.86,reason:'tree cover and heat'},{service:'Monitor urban areas',confidence:0.55,reason:'urban heat island'},{service:'Map and assess flooding',confidence:0.2,reason:'unlikely'}],
       questions:[],params:{place:'Marseille',bbox:[5.2,43.15,5.6,43.4],start:'2023-06-01',end:'2023-08-31',scale:'local',wants:'either'}}; }; return s; }
  if (n==='downloads') return { save: async()=>{} };
  return null; } };
"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','Which districts of Marseille lack tree cover and overheat in summer?'); pg.click('#go'); pg.wait_for_selector('#divgraph svg'); pg.wait_for_timeout(1200)
    print('nodes',pg.locator('.dv-node').count(),'edges',pg.locator('.dv-edge').count(),'bands',[x for x in pg.locator('.band summary').all_inner_texts()])
    pg.locator('.band').first.locator('summary').click(); pg.locator('.band').nth(1).locator('summary').click()
    sec=pg.locator('#sdiv'); sec.scroll_into_view_if_needed(); pg.wait_for_timeout(300); sec.screenshot(path=os.path.join(HERE,'out','div1.png'))
    pg.locator('.dv-node[data-kind="service"]').first.click(); pg.wait_for_timeout(200); pg.locator('#divgraph').screenshot(path=os.path.join(HERE,'out','div2.png'))
    print('dimmed after click',pg.locator('.dv-node.dv-dim').count())
    row=pg.locator('.layer').first; row.locator('button',has_text='How to get it').click(); pg.wait_for_timeout(1500)
    panel=row.locator('.panel'); print('buttons',panel.locator('.row button').all_inner_texts(), 'run disabled',panel.locator('button',has_text='Run request').is_disabled())
    panel.locator('button.info').click(); print('info:',panel.locator('.warn').inner_text()[:90])
    mp=panel.locator('.map'); mp.scroll_into_view_if_needed(); pg.wait_for_timeout(500); mp.screenshot(path=os.path.join(HERE,'out','map1.png'))
    # inland: Ahr valley
    for i,v in enumerate(['6.8','50.3','7.3','50.6']): panel.locator('.grid4 input').nth(i).fill(v)
    panel.locator('button',has_text='Fit box').click(); pg.wait_for_timeout(400); panel.locator('button',has_text='−').click(); pg.wait_for_timeout(300); mp.screenshot(path=os.path.join(HERE,'out','map2.png'))
    print('errors',errs[:5]); b.close()
