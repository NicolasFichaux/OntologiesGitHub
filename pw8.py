import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
import json,re
src=open(os.path.join(HERE,'pw7.py')).read(); POS=re.search(r'^POS=(.*?)\nPOS2',src,re.S|re.M).group(1)
POS=eval(POS.replace('None','None')); PIL={"overall":"ok","matches":[{"code":"S3P2","fit":"strong","why":"w","gaps":"g"}]}
with sync_playwright() as p:
    b=p.chromium.launch()
    # A: chat preview where the API fetch is blocked but window.claude.complete exists
    pg=b.new_page(viewport={'width':1180,'height':900}); pg.route('https://api.anthropic.com/**',lambda r:r.abort())
    pg.add_init_script("window.claude={complete:async p=>/e-shape pilot services/.test(p)?'%s':'Sure: '+'%s'};"%(json.dumps(PIL).replace("'","\\'"),json.dumps(POS).replace("'","\\'")))
    pg.goto(PAGE); pg.wait_for_timeout(700)
    pg.fill('#need','solar rooftops in Toulouse as per the energy plan'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000)
    print('A fallback to complete -> services',pg.locator('#results .svc').count(),'pilots',pg.locator('#pilots .svc').count())
    c=pg.locator('#regs .svc').first; c.locator('button',has_text='Read it on the web').click(); pg.wait_for_timeout(600)
    print('A web read ->',c.locator('.row .note').first.inner_text()[:230])
    # B: nothing available
    pg2=b.new_page(viewport={'width':1180,'height':900}); pg2.route('https://api.anthropic.com/**',lambda r:r.abort())
    pg2.goto(PAGE); pg2.wait_for_timeout(700)
    pg2.fill('#need','solar rooftops'); pg2.click('#go'); pg2.wait_for_timeout(1200); print('B ->',pg2.inner_text('#status'))
    # C: API answers 401
    pg3=b.new_page(viewport={'width':1180,'height':900}); pg3.route('https://api.anthropic.com/**',lambda r:r.fulfill(status=401,body='{}'))
    pg3.goto(PAGE); pg3.wait_for_timeout(700)
    pg3.fill('#need','solar rooftops'); pg3.click('#go'); pg3.wait_for_timeout(1200); print('C ->',pg3.inner_text('#status')[-120:])
    b.close()
