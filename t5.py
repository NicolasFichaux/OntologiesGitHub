import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
import json
req=json.load(open(os.path.join(HERE,'data','req_example.json')))
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=150)
at.session_state["nav_request"]=req
at.run(); assert not at.exception, at.exception
print('bbox N,S,W,E:',[at.number_input(key=k).value for k in ('bb_n','bb_s','bb_w','bb_e')],'| dates',at.date_input(key='d0').value,at.date_input(key='d1').value)
print('search collection:',next(t for t in at.text_input if t.key=='s_cid').value,'| msg:',[i.value for i in at.info][:1],'| warnings',[w.value[:80] for w in at.warning],'| errors',[e.value[:120] for e in at.error])
# order-type request
at2=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=150); at2.session_state["nav_request"]={**req,"collection":"EO.ECMWF.DAT.CAMS_SOLAR_RADIATION_TIMESERIES","mode":"order"}; at2.run(); assert not at2.exception
print('order collection:',next(t for t in at2.text_input if t.key=='o_cid').value)
# default run still fine
at3=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=150).run(); assert not at3.exception; print('default bbox',at3.number_input(key='bb_n').value,'errors',[e.value[:80] for e in at3.error])
