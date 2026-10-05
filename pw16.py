import os
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,'out'),exist_ok=True)
PAGE='file://'+os.path.abspath(os.path.join(HERE,'..','dist','earth-data-navigator.html'))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(PAGE); pg.wait_for_timeout(700)
    tests=["îlots de chaleur urbains","température de surface de la mer","land surface temperature in summer","canopée des arbres","pente des toits","rayonnement solaire","hauteur des bâtiments","air temperature"]
    print({t:pg.evaluate("(n)=>{const r=recipeFor({name:n}); return r?r.key:null}",t) for t in tests})
    print('by variable:',pg.evaluate("recipeFor({name:'x',variable:'Land surface temperature'}).key"),'| recipes in page:',pg.evaluate("DATA.PR.items.map(r=>r.key)"))
    print('errors',errs); b.close()
