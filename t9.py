import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
at2=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=240).run()
at2.text_input(key="proto_ingr").set_value("pente du terrain").run()
sel=[s for s in at2.selectbox if s.label=='Recipe'][0]; print('manual recipe auto:',sel.value)
at2.button(key="proto_go").click().run(); assert not at2.exception, at2.exception
md=[m.value for m in at2.markdown]
print('terrain title:',[m for m in md if m.startswith('###')][:1],'| errors',[e.value[:100] for e in at2.error])
print('steps:',[m[:95].replace('\n',' ') for m in md if m[:2] in ('1.','2.','3.')])
at2.text_input(key="proto_ingr").set_value("hauteur des bâtiments").run()
print('unknown ->',[i.value[:90] for i in at2.info if 'No recipe' in i.value])
at2.text_input(key="proto_ingr").set_value("rayonnement solaire").run(); at2.button(key="proto_go").click().run()
print('solar ->',[m.value for m in at2.markdown if m.value.startswith('###')][:1],'| errors',[e.value[:160] for e in at2.error])
