import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1180,'height':900}); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script("window.claude={use:async n=>{if(n==='sample'){const s=async()=>({text:''});s.json=async p=>({});return s;}return null;}};")
    pg.goto(PAGE); pg.wait_for_timeout(700)
    pg.click('summary:has-text("Choose a service yourself")'); pg.select_option('#manual','Map and assess flooding'); pg.uncheck('#optPilots'); pg.click('#manualGo'); pg.wait_for_timeout(600)
    st=lambda: pg.evaluate("({sel:document.getElementById('manual').value, idx:document.getElementById('manual').selectedIndex, open:document.querySelector('#s1 details').open, pilots:document.getElementById('optPilots').checked, s3:!document.getElementById('s3').hidden})")
    print('before reset',st()); pg.click('#reset'); pg.wait_for_timeout(200); print('after reset ',st()); print('errors',errs); b.close()
