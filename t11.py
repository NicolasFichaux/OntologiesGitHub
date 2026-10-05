import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
plan={"prototype_plan":1,"recipe":"surface_temperature","ingredient":"îlots de chaleur","place":"Marseille","bbox":[5.30,43.22,5.50,43.36],"start":"2025-07-01","end":"2025-08-31","need":"district","params":{}}
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240); at.session_state["nav_request"]=plan; at.run(); assert not at.exception, at.exception
print('recipe:',[s.value for s in at.selectbox if s.label=='Recipe'],'| outline lines:',len([m for m in at.markdown if m.value.startswith('- :')]))
at.button(key="proto_go").click().run(); assert not at.exception, at.exception
print('title:',[m.value for m in at.markdown if m.value.startswith('###')][:1],'| errors',[e.value[:120] for e in at.error])
print('figures:',[list(d.value.iloc[:3,1]) for d in at.dataframe if 'Key figure' in d.value.columns][:1])
