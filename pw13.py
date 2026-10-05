import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
src=open(os.path.join(HERE,'pw9b.py')).read().split('with sync_playwright')[0]
exec(src)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(800)
    pg.fill('#need','solar rooftops on public buildings in Toulouse'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(1600)
    card=pg.locator('#results .svc').first
    card.locator('button',has_text='Show all').click(); pg.wait_for_timeout(200)
    rows=card.locator('.layer'); n=rows.count()
    off=[(i,rows.nth(i).locator('.ttl').inner_text()[:50]) for i in range(n) if rows.nth(i).locator('.badge',has_text='Does not cover your area').count()]
    print('layers',n,'| off-area rows (position, title):',off)
    if off: print('   text:',rows.nth(off[0][0]).locator('.why').first.inner_text()[:170])
    print('first 4:',[rows.nth(i).locator('.ttl').inner_text()[:40] for i in range(4)])
    print('graph has Energy Indicators:',any('Energy Indicators' in (n.get_attribute('aria-label') or '') for n in pg.locator('.dv-node').all()),'| table has it:','ENERGY_INDICATORS' in pg.inner_text('#asmTable'))
    print('errors',errs[:5]); b.close()
