import sys, json, os, glob, re
import netCDF4
root = sys.argv[1]
# map file -> cross section type from configs
types = {}
for cfg in [os.path.join(root,'data','photolysis_rate_constants.json'), os.path.join(root,'examples','tuv_5_4.json')]:
    try: txt = open(cfg, encoding='utf-8').read()
    except Exception as e: print('cfg fail', cfg, e); continue
    def walk(o):
        if isinstance(o, dict):
            t = o.get('type')
            nd = o.get('netcdf files') or o.get('netcdf file')
            if t and nd:
                items = nd if isinstance(nd, list) else [nd]
                for it in items:
                    fn = it.get('file path') if isinstance(it, dict) else it
                    if fn: types.setdefault(os.path.basename(fn), set()).add(t)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    try: o = json.loads(txt)
    except Exception: o = json.loads("{"+txt+"}")
    walk(o)
for sub in ['cross_sections','quantum_yields']:
    for f in sorted(glob.glob(os.path.join(root,'data',sub,'*.nc'))):
        d = netCDF4.Dataset(f)
        dims = {k: len(v) for k, v in d.dimensions.items()}
        T = list(d.variables['temperature'][:]) if 'temperature' in d.variables else None
        var = [k for k in d.variables if k.endswith('parameters')]
        hdr = d.variables[var[0]].getncattr('hdr') if var and 'hdr' in d.variables[var[0]].ncattrs() else ''
        wlk=[k for k in d.variables if 'wavelength' in k.lower() or k.lower() in ('wl','lambda')]
        if not wlk: print(sub[:2], os.path.basename(f), dims, list(d.variables), 'NO-WL'); continue
        wl = d.variables[wlk[0]][:]
        print(sub[:2], os.path.basename(f), dims, T, f"{float(wl.min()):.1f}-{float(wl.max()):.1f}", sorted(types.get(os.path.basename(f), [])), '|', hdr.strip().split('\n')[0][:70])
