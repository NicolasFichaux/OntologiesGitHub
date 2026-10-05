import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
src=open(os.path.join(HERE,'pw9b.py')).read().split('with sync_playwright')[0]
exec(src)
MOCK=MOCK.replace("save:async()=>{}","save:async(o)=>{window.__saved=o}")
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','solar rooftops on public buildings in Toulouse'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(1600)
    print('table visible:',pg.locator('#assembly').is_visible(),'| rows',pg.locator('#asmTable tbody tr').count(),'| group headers',pg.locator('#asmTable tbody th').all_inner_texts())
    for i in range(min(14,pg.locator('#asmTable tbody tr').count())):
        tds=pg.locator('#asmTable tbody tr').nth(i).locator('td').all_inner_texts()
        if tds: print('   ',' | '.join(t[:44] for t in tds))
    pg.locator('#asmTable button',has_text='Get it').nth(2).click(); pg.wait_for_timeout(900)
    print('panel:',pg.locator('#asmPanel').is_visible(),'| title:',pg.locator('#asmPanel p').first.inner_text()[:90],'| map',pg.locator('#asmPanel canvas').count(),'| script has id:',('COLLECTION = "EO.' in pg.locator('#asmPanel pre').inner_text()))
    pg.click('#asmSave'); pg.wait_for_timeout(200); sv=pg.evaluate("window.__saved"); print('saved:',sv['filename'],'| lines',sv['data'].count('\n')+1,'| first:',repr(sv['data'].split('\n')[0][:110]),'| second:',sv['data'].split('\n')[1][:150])
    t=pg.locator('#assembly'); t.scroll_into_view_if_needed(); pg.wait_for_timeout(300); pg.locator('#asmTable').screenshot(path=os.path.join(HERE,'out','asm.png'))
    pg.click('#reset'); pg.wait_for_timeout(200); print('after reset: table hidden',not pg.locator('#assembly').is_visible(),'| panel children',pg.locator('#asmPanel > *').count())
    # manual path, analysis failing -> no table
    print('errors',errs[:5]); b.close()
