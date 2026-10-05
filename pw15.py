import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
import json
src=open(os.path.join(HERE,'pw9b.py')).read().split('with sync_playwright')[0]
exec(src)
DRAFT={"title":"Hauteur du bâti à partir du modèle de surface","feasible":"partly","steps":[{"text":"Lire le modèle de surface Copernicus sur la zone","nature":"named"},{"text":"Soustraire une estimation du sol par filtre minimum sur 300 m","nature":"choice"},{"text":"Lire la différence comme hauteur des bâtiments","nature":"interpretation"},{"text":"x","nature":"weird"}],
       "data":["EO.DEM.DAT.COP-DEM_GLO-30-DGED","EO.INVENTED.ID"],"output":"Une carte des hauteurs relatives.","missing":["Un modèle à 1 m","Une validation"]}
MOCK=MOCK.replace("save:async()=>{}","save:async(o)=>{window.__saved=o}").replace("if(/Earth observation engineer/.test(p))","if(/You design a small prototype/.test(p)){window.__d=p;return %s;}if(/Earth observation engineer/.test(p))"%json.dumps(DRAFT))
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','solar rooftops on public buildings in Toulouse'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(1600)
    print('chips:',pg.locator('#protoChips .chip').all_inner_texts()); print('cues:',pg.locator('.dv-node text.cue').all_inner_texts())
    node=pg.locator('.dv-node[data-kind="variable"]',has_text='canopée').first; node.scroll_into_view_if_needed(); node.click(); pg.wait_for_timeout(400)
    pr=pg.locator('#proto'); print('panel:',pr.locator('h3').first.inner_text(),'|',pr.locator('p strong').first.inner_text())
    print('  warn:',[t[:100] for t in pr.locator('p.warn:visible').all_inner_texts()]); print('  where:',[t[:90] for t in pr.locator('h3:has-text("Where and when") + ul li').all_inner_texts()])
    print('  steps:',[li.locator('.badge').inner_text() for li in pr.locator('ol.steps li').all()],'| images:',pr.locator('img').count())
    pr.locator('button',has_text='Save the plan').click(); pg.wait_for_timeout(200); sv=pg.evaluate("window.__saved"); plan=json.loads(sv['data']); print('  saved:',sv['filename'],'|',{k:plan[k] for k in ('recipe','ingredient','bbox','need','service')}); open(os.path.join(HERE,'out','plan_example.json'),'w').write(sv['data'])
    pr.locator('button.info').click(); print('  why not here:',pr.locator('p.warn:visible').last.inner_text()[:110])
    pr.screenshot(path=os.path.join(HERE,'out','proto_plan.png'))
    pg.locator('#protoChips .chip',has_text='hauteur').click(); pg.wait_for_timeout(300)
    print('no recipe:',pr.locator('p.warn').first.inner_text()[:90]); pr.locator('button',has_text='Ask Claude to draft').click(); pg.wait_for_timeout(900)
    print('  draft:',pr.locator('p strong').first.inner_text(),'|',pr.locator('.badge').first.inner_text(),'| steps:',[li.locator('.badge').inner_text() for li in pr.locator('ol.steps li').all()])
    print('  data kept:',pr.locator('h3:has-text("Data it would read") + ul li').all_inner_texts(),'| banner:',pr.locator('p.warn').nth(1).inner_text()[:120])
    print('  prompt lists datasets:', 'none found' in pg.evaluate("window.__d") or 'EO.' in pg.evaluate("window.__d"))
    pr.locator('button',has_text='Save this draft').click(); pg.wait_for_timeout(200); d=json.loads(pg.evaluate("window.__saved")['data']); print('  draft saved: recipe',d['recipe'],'| steps',len(d['draft']['steps']))
    open(os.path.join(HERE,'out','plan_draft.json'),'w').write(pg.evaluate("window.__saved")['data'])
    pr.screenshot(path=os.path.join(HERE,'out','proto_draft.png'))
    pg.locator('#protoChips .chip',has_text='emprise').click(); pg.wait_for_timeout(200); print('local:',pr.locator('p').first.inner_text()[:80])
    pg.click('#reset'); pg.wait_for_timeout(200); print('after reset hidden:',not pg.locator('#protoPick').is_visible()); print('errors',errs[:5]); b.close()
