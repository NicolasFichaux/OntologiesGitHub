import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
import json
POS={"understanding":"Potentiel solaire des bâtiments publics de Toulouse.","actors":["service énergie de la ville de Toulouse"],
 "usages":[{"text":"sélectionner les bâtiments et parkings publics prioritaires","needs":[0]},{"text":"suivre la production une fois les panneaux posés","needs":[1]}],"references":[],
 "candidates":[{"service":"Map & monitor solar energy (solar farms)","confidence":0.85,"reason":"r","information":"potentiel solaire par bâtiment, avec ombrage","resolution":"bâtiment, environ 1 m","frequency":"","delay":""},
               {"service":"Forecasting sunlight exposure","confidence":0.6,"reason":"r","information":"rayonnement reçu chaque jour","resolution":"locale","frequency":"quotidien","delay":""}],
 "questions":[],"params":{"place":"Toulouse, France","bbox":[1.3,43.5,1.55,43.7],"start":None,"end":None,"scale":"local","wants":"either"}}
ANA={"analysis":[{"information":0,"ingredients":[
  {"name":"rayonnement solaire au sol","role":"énergie disponible","kind":"eo","variable":"Downward short-wave irradiance at Earth surface","service":"Map & monitor solar energy (solar farms)","resolution":""},
  {"name":"modèle numérique de surface (bâti et relief)","role":"pente, orientation, ombres portées","kind":"eo","variable":"Land surface topography","service":"Baseline mapping","resolution":"1 m"},
  {"name":"canopée des arbres","role":"ombrage par la végétation","kind":"eo","variable":"","service":"Monitor urban green & blue areas","resolution":"1 m"},
  {"name":"hauteur des bâtiments","role":"ombres","kind":"eo","variable":"Invented variable","service":"Invented service","resolution":""},
  {"name":"emprise des bâtiments publics","role":"savoir quels toits sont concernés","kind":"other","variable":"","service":"","resolution":""}]},
 {"information":1,"ingredients":[{"name":"couverture nuageuse","role":"variabilité","kind":"eo","variable":"Cloud cover","service":"","resolution":""}]}]}
PIL={"overall":"ok","matches":[{"code":"S3P2","fit":"partial","why":"w","gaps":"g"}]}
MOCK="window.__a=[];window.claude={use:async n=>{if(n==='sample'){const s=async()=>({text:''});s.json=async p=>{if(/e-shape pilot services/.test(p))return %s;if(/Earth observation engineer/.test(p)){window.__a.push(p);await new Promise(r=>setTimeout(r,600));return %s;}return %s;};return s;}if(n==='downloads')return{save:async()=>{}};return null;}};"%(json.dumps(PIL),json.dumps(ANA),json.dumps(POS))
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','solar rooftops on public buildings in Toulouse'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(1500)
    lab=lambda sel: [n.get_attribute('aria-label')[:75] for n in pg.locator(sel).all()]
    print('USES:',lab('.dv-node[data-kind="use"]')); print('INFO:',lab('.dv-node[data-kind="service"]')[:2])
    print('INGREDIENTS:',lab('.dv-node[data-kind="variable"]'))
    print('GAPS:',lab('.dv-node[data-gap="1"]')); print('OUT:',[x for x in lab('.dv-node[data-where="out"]') if 'local' in x or 'Tree' in x])
    print('DATA:',[x[:55] for x in lab('.dv-node[data-kind="data"]')])
    print('card ingredients:',pg.locator('[data-ingr="0"] li').count(),'|',pg.locator('[data-ingr="0"] li').nth(1).inner_text()[:150].replace('\n',' / '))
    print('ctxIngr:',repr(pg.input_value('#ctxIngr'))[:140])
    op=pg.locator('#workshops .svc',has_text='Operability'); print('operability:',op.locator('.badge').first.inner_text(),'|',[t[:90] for t in op.locator('ul.res').first.locator('li').all_inner_texts() if 'ngredient' in t])
    g=pg.locator('#divgraph'); g.scroll_into_view_if_needed(); pg.wait_for_timeout(300); g.screenshot(path=os.path.join(HERE,'out','div7.png')); c=pg.locator('#results .svc').first; c.scroll_into_view_if_needed(); pg.wait_for_timeout(200); c.screenshot(path=os.path.join(HERE,'out','card7.png')); pg.locator('#snap').screenshot(path=os.path.join(HERE,'out','snap7.png'))
    # only ingredients edited -> analysis only
    n0=pg.evaluate("window.__a.length"); pg.fill('#ctxIngr',pg.input_value('#ctxIngr')+'\nraccordement au réseau électrique'); pg.click('#ctxGo'); pg.wait_for_timeout(1200)
    print('analysis rerun:',pg.evaluate("window.__a.length")-n0,'| user ingredients in prompt:',pg.evaluate("/raccordement au réseau/.test(window.__a[window.__a.length-1])"))
    # reword usage with two disjoint lines -> two boxes at once
    pg.fill('#ctxUse','choisir les toits à équiper\npréparer le budget pluriannuel'); pg.click('#ctxGo'); pg.wait_for_timeout(250)
    print('immediate split:',lab('.dv-node[data-kind="use"]'))
    pg.wait_for_timeout(2500); print('errors',errs[:5]); b.close()
