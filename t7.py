import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); APPDIR=os.path.abspath(os.path.join(HERE,'..')); sys.path.insert(0,APPDIR); os.chdir(APPDIR)
import time, json
import ei_proto as ep
tests=[("veg Toulouse Jul 2024",{"ingredient":"canopée des arbres","bbox":[1.30,43.50,1.55,43.70],"start":"2024-07-01","end":"2024-07-10","need":"1 m"}),
       ("veg Lyon, no dates (last 60 days)",{"ingredient":"espaces verts","bbox":[4.75,45.68,4.95,45.82]}),
       ("veg large box (averaged)",{"recipe":"vegetation_index","bbox":[1.0,43.3,1.9,43.9],"start":"2025-06-01","end":"2025-08-31"}),
       ("terrain Grenoble two tiles",{"ingredient":"relief et pente","bbox":[5.85,45.10,6.10,45.30],"need":"1 m"}),
       ("solar Sevilla",{"ingredient":"rayonnement solaire","bbox":[-6.1,37.3,-5.8,37.5]}),
       ("solar at sea (must fail cleanly)",{"recipe":"solar_monthly","bbox":[-30.2,40.0,-30.0,40.2]}),
       ("unknown ingredient",{"ingredient":"hauteur des bâtiments","bbox":[1.3,43.5,1.55,43.7]})]
for name,plan in tests:
    t=time.time(); r=ep.run(plan,workdir=os.path.join(HERE,'out','run_')+name.split()[0]+str(len(name)))
    print(f"\n## {name}  ({time.time()-t:.0f} s)  ok={r['ok']}")
    if not r['ok']: print('   error:',r['error'][:200]); continue
    print('   recipe:',r['recipe'],'| image:',os.path.basename(r['image']),os.path.getsize(r['image'])//1024,'KB')
    for f in r['figures'][:4]: print('   -',f[0],':',f[1][:110])
    print('   see:',r['see'][1][:210]); print('   steps:',[s['how'] for s in r['steps']],'| warnings:',r['warnings'][:1])
