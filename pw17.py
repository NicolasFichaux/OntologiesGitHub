import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
src=open(os.path.join(HERE,'pw9b.py')).read().split('with sync_playwright')[0]
exec(src)
MOCK=MOCK.replace("s.json=async p=>{","s.json=async p=>{(window.__len=window.__len||[]).push([/e-shape pilot services/.test(p)?'pilots':/Earth observation engineer/.test(p)?'analysis':'positioning',p.length]);")
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); pg.add_init_script(MOCK); pg.goto(PAGE); pg.wait_for_timeout(700)
    pg.fill('#need','I need to implement solar rooftops on public buildings in Toulouse, as per the energy plan'); pg.click('#go'); pg.wait_for_selector('#pilots .svc',timeout=20000); pg.wait_for_timeout(1500)
    L=pg.evaluate("window.__len"); print(L); tot=sum(x[1] for x in L); print('total characters sent:',tot,'| about',round(tot/3.2/1000,1),'to',round(tot/2.6/1000,1),'thousand tokens'); b.close()
