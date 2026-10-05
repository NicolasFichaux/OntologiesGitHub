import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=200).run()
assert not at.exception, at.exception
# pick the solar service through the theme entry of the Applications tab
sb=[s for s in at.selectbox if s.label and 'service' in s.label.lower()]
print('selectboxes:',[s.label for s in at.selectbox][:8])
dfs=[d.value for d in at.dataframe]
print('dataframes:',len(dfs)); 
for d in dfs[:3]: print(list(d.columns)[:8], len(d))
print('errors',[e.value[:100] for e in at.error])
