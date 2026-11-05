"""Meaningful data invariants: finite numeric observations, ordered unique dates,
no future observations, genuine 12-month signal, cross-rate direction and units.
"""
import json,math
from pathlib import Path
from datetime import date
p=Path(__file__).resolve().parents[1]/'dist/data/macro.json';d=json.loads(p.read_text())
assert len(d['series'])>=10,'Too few official series'
for key,s in d['series'].items():
 pts=s['points'];dates=[x[0] for x in pts]
 assert pts and dates==sorted(set(dates)),key+' duplicate or unordered dates'
 assert all(math.isfinite(v) and dt<=date.today().isoformat() for dt,v in pts),key+' invalid observation'
 assert s['url'].startswith('https://'),key+' missing provenance'
 assert s['latestDate']==dates[-1]
s=d['series'].get('tw_signal')
if s:
 assert len(s['points'])>=12
 assert all(9<=v<=45 for _,v in s['points'])
 tail=s['points'][-12:];ordinals=[int(dt[:4])*12+int(dt[5:7]) for dt,_ in tail]
 assert all(b-a==1 for a,b in zip(ordinals,ordinals[1:])),'Signal must cover 12 consecutive months'
if all(k in d['series'] for k in ['twdjpy','usdtwd','usdjpy']):
 a=dict(d['series']['usdtwd']['points']);b=dict(d['series']['usdjpy']['points'])
 for dt,v in d['series']['twdjpy']['points'][-30:]:assert abs(v-b[dt]/a[dt])<1e-5
if d.get('cpiCategories'):assert d['cpiCategories']['unit']=='年增率 %'
print('Validated',len(d['series']),'official series; date, numeric, signal and FX invariants passed')
