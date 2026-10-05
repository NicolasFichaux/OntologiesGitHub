import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
MOCK = """
window.__n=0;
window.claude = { use: async (n) => {
  if (n==='sample'){ const s = async()=>({text:''}); s.json = async (p)=>{
     if (/e-shape pilot services/.test(p)) return {overall:'ok',matches:[{code:'S7P2',fit:'partial',why:'w',gaps:'g'}]};
     window.__n++; await new Promise(r=>setTimeout(r,1500));
     if (window.__fail) throw Object.assign(new Error('x'),{code:'rate_limited'});
     // the model keeps the SAME usage and services even after a rewording
     return {understanding:'Find districts that overheat.',actor:'City planning department',usage:'Decide where to plant trees first',
       candidates:[{service:'Monitor urban green & blue areas',confidence:0.86,reason:'r',information:'Tree canopy share per district',resolution:'about 10 m',frequency:'yearly',delay:''}],
       questions:[],params:{place:'Marseille',bbox:[5.2,43.15,5.6,43.4],start:'2023-06-01',end:'2023-08-31',scale:'local',wants:'either'}}; }; return s; }
  if (n==='downloads') return { save: async()=>{} };
  return null; } };
"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','Which districts of Marseille overheat?'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(500)
    use=lambda: pg.locator('.dv-node[data-kind="use"]').first.get_attribute('aria-label')
    print('bands left:',pg.locator('.band').count(),'| use node:',use())
    pg.fill('#ctxUse','Justify the tree-planting budget to elected officials'); pg.click('#ctxGo'); pg.wait_for_timeout(300)
    print('at once -> use node:',use(),'| button:',pg.inner_text('#ctxGo'),'| status:',pg.inner_text('#divstatus')[:60])
    pg.wait_for_timeout(2500)
    print('after   -> use node:',use(),'| button:',pg.inner_text('#ctxGo'),'| note visible:',pg.locator('#divchange').is_visible(),'|',pg.inner_text('#divchange')[:80])
    pg.evaluate("window.__fail=true"); pg.fill('#ctxUse','Second wording'); pg.click('#ctxGo'); pg.wait_for_timeout(2300)
    print('on failure -> use node:',use(),'| status:',pg.inner_text('#divstatus')[:110],'| button:',pg.inner_text('#ctxGo'))
    print('workshops',pg.locator('#workshops .svc').count(),'errors',errs[:5]); b.close()
