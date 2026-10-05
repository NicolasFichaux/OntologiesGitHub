import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
plan={"prototype_plan":1,"ingredient":"canopée des arbres","service":"Monitor urban green & blue areas","place":"Toulouse","bbox":[1.36,43.56,1.50,43.65],"start":"2024-07-01","end":"2024-07-10","need":"1 m","params":{}}
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240); at.session_state["nav_request"]=plan; at.run()
assert not at.exception, at.exception
print('sidebar bbox:',[at.number_input(key=k).value for k in ('bb_w','bb_s','bb_e','bb_n')],'| msg:',[i.value[:70] for i in at.info][:1])
sel=[s for s in at.selectbox if s.label=='Recipe'][0]; print('recipe auto:',sel.value)
at.button(key="proto_go").click().run()
assert not at.exception, at.exception
md=[m.value for m in at.markdown]
print('title:',[m for m in md if m.startswith('###')][:1]); print('errors:',[e.value[:120] for e in at.error],'| warnings:',[w.value[:90] for w in at.warning])
steps=[m for m in md if m[:2] in ('1.','2.','3.','4.','5.','6.','7.')]; print('steps:',len(steps)); print('  ',steps[0][:230].replace('\n',' ')); print('  ',steps[-1][:200].replace('\n',' '))
print('figures table:',[list(d.value.iloc[:,1])[:3] for d in at.dataframe if 'Key figure' in d.value.columns][:1])
print('missing:',[m[:80] for m in md if m.startswith('- ') and ('Trees' in m or 'detail' in m)][:2])
# manual: terrain, no plan
at2=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240).run()
at2.text_input(key="proto_ingr").set_value("pente du terrain").run()
sel=[s for s in at2.selectbox if s.label=='Recipe'][0]; print('manual recipe auto:',sel.value)
at2.button(key="proto_go").click().run(); assert not at2.exception, at2.exception
print('terrain title:',[m.value for m in at2.markdown if m.value.startswith('###')][:1],'| errors',[e.value[:100] for e in at2.error])
at3=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240).run(); at3.text_input(key="proto_ingr").set_value("hauteur des bâtiments").run()
print('unknown ->',[i.value[:90] for i in at3.info if 'No recipe' in i.value])
