import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
import json
POS={"understanding":"Solar rooftops on public buildings in Toulouse.","actor":"City of Toulouse","usage":"plan rooftop PV on public buildings","references":[{"mention":"the energy plan","guess":"Plan Climat Air Énergie Territorial","issuer":"Toulouse Métropole"}],
 "candidates":[{"service":"Map & monitor solar energy (solar farms)","confidence":0.85,"reason":"solar","information":"solar potential per public roof","resolution":"building scale","frequency":"","delay":""}],
 "questions":[],"params":{"place":"Toulouse","bbox":[1.3,43.5,1.55,43.7],"start":None,"end":None,"scale":"local","wants":"either"}}
POS2=dict(POS); POS2["candidates"]=POS["candidates"]+[{"service":"Monitor urban green & blue areas","confidence":0.6,"reason":"greening","information":"vegetation cover near public buildings","resolution":"10 m","frequency":"yearly","delay":""}]
REG={"identified":True,"title":"Plan Climat Air Énergie Territorial","issuer":"Toulouse Métropole","date":"2019","summary":"Sets 2030 targets.","obligations":["PV on new public buildings"],
 "related_needs":[{"need":"prioritise energy renovation of public buildings","why":"renovation plan"},{"need":"green public spaces","why":"vegetation works"}],"sources":[{"title":"Toulouse Métropole","url":"https://metropole.toulouse.fr/x"},{"title":"bad","url":"javascript:alert(1)"}],"caveat":"which edition"}
PIL={"overall":"ok","matches":[{"code":"S3P2","fit":"strong","why":"w","gaps":"g"}]}
MOCK="window.__p=[];window.claude={use:async n=>{if(n==='sample'){const s=async()=>({text:''});s.json=async p=>{window.__p.push(p);if(/e-shape pilot services/.test(p))return %s;if(/They refer to/.test(p))return %s;return /Regulatory or planning context/.test(p)?%s:%s;};return s;}if(n==='downloads')return{save:async()=>{}};return null;}};"%(json.dumps(PIL),json.dumps(REG),json.dumps(POS2),json.dumps(POS))
def flow(pg,label,web):
    pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','I need to implement solar rooftops on public buildings in Toulouse, as per the energy plan'); pg.click('#go'); pg.wait_for_selector('#regs .svc',timeout=20000); pg.wait_for_timeout(700)
    c=pg.locator('#regs .svc').first; btn=c.locator('button',has_text='Read it on the web')
    print(label,'| card:',c.locator('h3').inner_text(),'| web button enabled:',btn.is_enabled(),'| info btn:',c.locator('button.info').count())
    if web: btn.click()
    else:
        c.locator('summary',has_text='paste').click(); c.locator('textarea').fill('Action 12: solar panels on all new public buildings. Action 13: energy renovation of public buildings.'); c.locator('button',has_text='Analyse this text').click()
    pg.wait_for_selector('#regs .chip',timeout=20000); c=pg.locator('#regs .svc').first
    print('   result:',c.locator('p strong').first.inner_text(),'| chips',c.locator('.chip').count(),'| source links',c.locator('p.note a').count(),'|',c.locator('p.note',has_text='Source').inner_text()[:70])
    c.locator('.chip').first.click(); c.locator('button',has_text='Use this context').click(); pg.wait_for_timeout(1500)
    print('   after apply: info nodes',pg.locator('.dv-node[data-kind="service"]').count(),'| reg node:',[n.get_attribute('aria-label')[:60] for n in pg.locator('.dv-node[data-kind="market"]').all() if 'regulation' in n.get_attribute('aria-label')],'| note:',pg.inner_text('#divchange')[:70])
with sync_playwright() as p:
    b=p.chromium.launch(); errs=[]
    pg=b.new_page(viewport={'width':1180,'height':900}); pg.on('pageerror', lambda e: errs.append(str(e))); pg.add_init_script(MOCK); flow(pg,'PUBLISHED',False)
    print('   context sent to Claude:',pg.evaluate("window.__p.some(p=>/Regulatory or planning context/.test(p)&&/prioritise energy renovation/.test(p))"))
    # chat preview: no window.claude, Anthropic API intercepted
    calls=[]
    def handle(route):
        body=json.loads(route.request.post_data); t=body['messages'][0]['content']; calls.append({'tools':bool(body.get('tools')),'model':body['model'],'max':body['max_tokens']})
        out= PIL if 'e-shape pilot services' in t else REG if 'They refer to' in t else (POS2 if 'Regulatory or planning context' in t else POS)
        route.fulfill(status=200,content_type='application/json',body=json.dumps({"content":[{"type":"text","text":"Here you go:\n```json\n"+json.dumps(out)+"\n```"}]}))
    pg2=b.new_page(viewport={'width':1180,'height':900}); pg2.on('pageerror', lambda e: errs.append(str(e))); pg2.route('https://api.anthropic.com/**',handle); flow(pg2,'PREVIEW  ',True)
    print('   API calls:',calls)
    c=pg2.locator('#regs .svc').first; c.scroll_into_view_if_needed(); c.screenshot(path=os.path.join(HERE,'out','reg.png'))
    print('errors',errs[:5]); b.close()
