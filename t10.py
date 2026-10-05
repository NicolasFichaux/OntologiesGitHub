import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
import json
from streamlit.testing.v1 import AppTest
plan=json.load(open(os.path.join(HERE,'data','plan_example.json'))); plan['bbox']=[1.38,43.57,1.48,43.64]; plan['start']='2025-07-01'; plan['end']='2025-08-15'
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240); at.session_state["nav_request"]=plan; at.run(); assert not at.exception, at.exception
print('plan from the page ->',[s.value for s in at.selectbox if s.label=='Recipe'],'| dates',at.date_input(key='d0').value,at.date_input(key='d1').value)
at.button(key="proto_go").click().run(); assert not at.exception, at.exception
print('  generated:',[d.value.iloc[0,1] for d in at.dataframe if 'Key figure' in d.value.columns],'| errors',[e.value[:100] for e in at.error])
dr=json.load(open(os.path.join(HERE,'data','plan_draft.json')))
at2=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240); at2.session_state["nav_request"]=dr; at2.run(); assert not at2.exception, at2.exception
md=[m.value for m in at2.markdown]
print('draft plan ->',[m for m in md if m.startswith('#### Draft')],'| steps',len([m for m in md if m[:2] in ('1.','2.','3.','4.')]),'| warning',[w.value[:60] for w in at2.warning][:1])
