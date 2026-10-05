import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
from streamlit.testing.v1 import AppTest
at=AppTest.from_file(os.path.join(APPDIR,"hda_app.py"),default_timeout=120).run()
assert not at.exception, at.exception
print('tabs ok; errors:',[e.value for e in at.error], 'warnings:',[w.value[:80] for w in at.warning])
def sb(label): return next(x for x in at.selectbox if x.label==label)
print('market options',sb('Market').options[:3],'| sector',sb('Sector').value,'| services',len(sb('EARSC service').options))
# theme entry -> flooding
at.radio(key='app_entry').set_value('Theme (what is observed)').run(); assert not at.exception, at.exception
sb('Domain').set_value('Disasters & Geohazards').run()
sv=sb('EARSC service'); sv.set_value('Map and assess flooding').run(); assert not at.exception, at.exception
dfs=[d.value for d in at.dataframe]; print('tables',[len(d) for d in dfs][:3]); print(dfs[0].head(3).to_string())
pick=next(x for x in at.selectbox if x.key and x.key.startswith('app_pick_')); pick.set_value('EO.ESA.DAT.SENTINEL-1.L1_GRD').run()
next(b for b in at.button if b.key=='app_use').click().run(); assert not at.exception, at.exception
print('cid',at.session_state['cid'],'| s_cid',at.session_state['s_cid'],'| o_cid',at.session_state['o_cid'],'| success:',[x.value for x in at.success])
print('search tab collection field:',next(t for t in at.text_input if t.key=='s_cid').value)
print('collection sheet expanders:',[e.label for e in at.expander if 'Applications' in e.label])
# free text
at.radio(key='app_entry').set_value('Free text').run(); at.text_input(key='app_ft').set_value('urban heat island').run(); assert not at.exception, at.exception
print('free text ->',sb('EARSC service').options[:4])
# market w/o services
at.radio(key='app_entry').set_value('Market (who uses it)').run(); sb('Market').set_value('Urban Development').run(); assert not at.exception, at.exception
print('Urban Development/',sb('Sector').value,'->',sb('EARSC service').options[:6])
# ECMWF pick -> order tab
at.radio(key='app_entry').set_value('Theme (what is observed)').run(); sb('Domain').set_value('Built Environment').run()
sb('EARSC service').set_value('Map & monitor solar energy (solar farms)').run()
pick=next(x for x in at.selectbox if x.key and x.key.startswith('app_pick_')); pick.set_value('EO.ECMWF.DAT.CAMS_SOLAR_RADIATION_TIMESERIES').run()
next(b for b in at.button if b.key=='app_use').click().run(); assert not at.exception, at.exception
print('o_cid',at.session_state['o_cid'],'errors:',[e.value[:150] for e in at.error])
