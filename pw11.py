import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script("window.claude={use:async n=>{if(n==='sample'){const s=async()=>({text:''});s.json=async p=>{ if(/Earth observation engineer/.test(p)) throw Object.assign(new Error('x'),{code:'rate_limited'}); return {overall:'',matches:[]}; };return s;}return null;}};")
    pg.goto(PAGE); pg.wait_for_timeout(800)
    print('snapshot line:',pg.inner_text('#snap')[:230])
    for svc in ['Map & monitor solar energy (solar farms)','Map and assess flooding','Detect and monitor ground movement']:
        pg.click('#reset'); pg.click('summary:has-text("Choose a service yourself")'); pg.select_option('#manual',svc); pg.click('#manualGo'); pg.wait_for_timeout(1200)
        rows=pg.locator('#results .layer')
        top=[rows.nth(i).locator('.ttl').inner_text()[:42]+' | '+rows.nth(i).locator('.badge').first.inner_text()+' | '+rows.nth(i).locator('.why').last.inner_text()[:95] for i in range(min(4,rows.count()))]
        txt=pg.inner_text('#results')
        print('\n##',svc,'| layers',rows.count(),'| "id matches" shown:', 'id matches' in txt,'| TROPOMI in first 6:', any('TROPOMI' in rows.nth(i).inner_text() for i in range(min(6,rows.count()))))
        [print('   ',t) for t in top]
        print('   resolution lines:',pg.locator('#results .why',has_text='Resolution:').count(),'| graph nodes',pg.locator('.dv-node').count(),'| outside-DL nodes',[n.get_attribute('aria-label')[:60] for n in pg.locator('.dv-node[data-where="out"]').all()])
        print('   analysis status:',pg.inner_text('#anastatus')[:120])
    print('errors',errs[:5]); b.close()
