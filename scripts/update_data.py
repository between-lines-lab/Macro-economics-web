#!/usr/bin/env python3
"""Daily official-source ingestion. Failed sources preserve last successful data.
No interpolated/fabricated observations; all units and transformations recorded.
"""
import concurrent.futures as cf, csv, io, json, re, os, zipfile, sys, math
from pathlib import Path
from datetime import datetime, timezone, date
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'dist/data/macro.json'
NOW=datetime.now(timezone.utc).isoformat(); TODAY=date.today().isoformat()
OLD=json.loads(OUT.read_text()) if OUT.exists() else {'series':{},'news':[],'calendar':[]}
DATA={'generatedAt':NOW,'schedule':'每日 21:30 Asia/Taipei','series':dict(OLD.get('series',{})),'news':OLD.get('news',[]),'calendar':OLD.get('calendar',[]),'sources':[]}

def get(url):
 s=requests.Session();s.headers['User-Agent']='MacroLens/1.0 (public economic statistics; daily refresh)'
 s.mount('https://',HTTPAdapter(max_retries=Retry(total=2,backoff_factor=.6,status_forcelist=[429,500,502,503,504])))
 r=s.get(url,timeout=(10,35));r.raise_for_status();return r

def soup(url):return BeautifulSoup(get(url).content,'html.parser')
def number(x):
 try:
  v=float(str(x).replace(',','').replace('%','').strip());return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None

def month(s):
 s=str(s).strip().replace('M','-')
 if re.fullmatch(r'\d{5}',s):return f'{int(s[:3])+1911}-{s[3:]}-01'
 if re.fullmatch(r'\d{6}',s):return f'{s[:4]}-{s[4:]}-01'
 a=re.search(r'(\d{2,4})[年./-]\s*(\d{1,2})',s)
 if a:
  y=int(a[1]);return f'{y+1911 if y<1911 else y:04d}-{int(a[2]):02d}-01'
 raise ValueError('Unknown month '+s)
def day(s):
 a=re.findall(r'\d+',str(s))
 if len(a)==1 and len(a[0]) in [7,8]:
  z=a[0];y=int(z[:-4]);return f'{y+1911 if y<1911 else y:04d}-{z[-4:-2]}-{z[-2:]}'
 y=int(a[0]);return f'{y+1911 if y<1911 else y:04d}-{int(a[1]):02d}-{int(a[2]):02d}'

def add(key,title,unit,group,points,source,url,frequency='月',note='',published=None):
 valid={str(d):round(float(v),6) for d,v in points if number(v) is not None and str(d)<=TODAY}
 if not valid:raise ValueError(key+': no valid data')
 prior=DATA['series'].get(key,{}).get('points',[])
 merged={d:v for d,v in prior};merged.update(valid)
 points=sorted(merged.items()); points=[p for p in points if p[0]>='2000-01-01']
 DATA['series'][key]={'id':key,'title':title,'unit':unit,'group':group,'frequency':frequency,'source':source,'url':url,'note':note,'published':published,'checkedAt':NOW,'points':points,'latestDate':points[-1][0]}

def yoy(points):
 m=dict(points);out=[]
 for d,v in points:
  y=f'{int(d[:4])-1}{d[4:]}'
  if y in m and m[y]:out.append((d,(v/m[y]-1)*100))
 return out

def dgbas():
 base='https://www.stat.gov.tw/';home=soup(base)
 for sid,n,mapping in [('t.2',3581,{'消費者物價指數年增率':('tw_cpi','CPI年增率'),'核心CPI年增率':('tw_core','核心CPI年增率'),'消費者物價指數季調後月增率':('tw_cpi_mom','CPI月增率（季調）')}),('t.3',3582,{'失業率':('tw_unemployment','失業率'),'失業率(經季節調整後)':('tw_unemployment_sa','失業率（季調）'),'勞動力參與率':('tw_labor','勞動力參與率')})]:
  u=f'{base}Point.aspx?sid={sid}&n={n}&sms=11480';s=soup(u);j=json.loads(s.select_one('input[id$=hidChartData]')['value'])
  for title,(key,name) in mapping.items():
   x=max([x for x in j if x['Title']==title],key=lambda x:len(x['data']))
   pts=[(month(p['Date']),number(p['Value'])) for p in x['data'] if '月' in p.get('Title','')]
   add(key,name,'%', '台灣經濟',pts,'主計總處',u,note='年增率未季調；月增率與失業率季調序列另列。')
 # Latest official CPI release: derive the attachment URL from current announcement.
 links=[a for a in home.select('a[href]') if re.search(r'\d+年\d+月消費者物價指數',a.get_text())]
 if links:
  a=links[0];u=urljoin(base,a['href']);s=soup(u);text=a.get_text(' ',strip=True);per=month(re.search(r'\d+年\d+月',text)[0]);pub=re.search(r'(\d{3})-(\d{2})-(\d{2})',text)
  pub=f'{int(pub[1])+1911}-{pub[2]}-{pub[3]}' if pub else None
  for k in ['tw_cpi','tw_core','tw_cpi_mom']:DATA['series'][k]['published']=pub
  attach=[urljoin(u,a['href']) for a in s.select('a[href]') if re.search(r't\d+_1\.xlsx',a['href'])]
  if attach:
   import pandas as pd
   df=pd.read_excel(io.BytesIO(get(attach[0]).content),header=None);pts=[]
   for _,row in df.iterrows():
    label=str(row.iloc[1]).strip()
    if re.match(r'^[一二三四五六七][.．、]',label) and any(x in label for x in ['食物類','衣著類','居住類','交通','醫藥','教養','雜項']):
     label=re.sub(r'^[一二三四五六七][.．、]\s*','',label);val=number(row.iloc[6])
     if val is not None:pts.append([label,val])
   if pts:DATA['cpiCategories']={'period':per,'points':pts,'source':'主計總處','url':u,'published':pub,'checkedAt':NOW,'unit':'年增率 %'}
 # GDP: MOEA's published quarterly indicator cards, independently sourced from DGBAS.
 u='https://www.moea.gov.tw/Mns/dos/home/Home.aspx';s=soup(u);txt=s.get_text(' ',strip=True);pts=[]
 for y,q,pub,v in re.findall(r'(\d{3})年第(\d)季(?:\s*\([a-z]\))?\s*經濟成長率\s*(\d+/\d+/\d+)發布\s*([\d.]+)[%％]',txt):
  pts.append((f'{int(y)+1911}-{(int(q)-1)*3+1:02d}-01',float(v)))
 if pts:add('tw_gdp','實質GDP年增率','%','台灣經濟',pts,'主計總處／經濟部',u,'季','官方首頁可取得之近期季度；未以插值延伸歷史。')
 # current news with exact source URLs and official release dates
 news=[]
 for a in home.select('a[href]'):
  t=a.get_text(' ',strip=True);m=re.match(r'(\d{3})-(\d{2})-(\d{2})\s+(.+)',t)
  if m and 'News_Content' in a['href']:
   d=f'{int(m[1])+1911}-{m[2]}-{m[3]}'
   if d<=TODAY:news.append({'date':d,'title':m[4],'source':('國家發展委員會' if 'ndc.gov.tw' in a['href'] else '中央銀行' if 'cbc.gov.tw' in a['href'] else '主計總處'),'region':'台灣','url':urljoin(base,a['href'])})
 return news

def ndc():
 u='https://data.gov.tw/dataset/6099';s=soup(u);h=next(a['href'] for a in s.select('a[href]') if 'icon=.zip' in a['href']);z=zipfile.ZipFile(io.BytesIO(get(h).content));name=next(n for n in z.namelist() if n.endswith('景氣指標與燈號.csv') and 'schema' not in n)
 rows=list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
 add('tw_signal','景氣燈號綜合判斷分數','分','台灣經濟',[(month(r['Date']),number(r['景氣對策信號綜合分數'])) for r in rows],'國家發展委員會',u,note='藍9–16、黃藍17–22、綠23–31、黃紅32–37、紅38–45。')
 add('tw_leading','領先指標（不含趨勢）','指數','台灣經濟',[(month(r['Date']),number(r['領先指標不含趨勢指數'])) for r in rows],'國家發展委員會',u)

def moea():
 u='https://service.moea.gov.tw/EE520/opendata/d.csv';rows=list(csv.DictReader(io.StringIO(get(u).content.decode('utf-8-sig'))))
 for industry,key,title in [('工業','tw_industry','工業生產年增率'),('製造業','tw_manufacturing','製造業生產年增率')]:
  pts=[(month(r['資料期(民國年)']),number(r['統計值(指數)'])) for r in rows if r['行業別'].strip()==industry and r['統計項目'].strip()=='生產指數' and number(r['統計值(指數)']) is not None]
  if pts:add(key,title,'%','台灣經濟',yoy(pts),'經濟部統計處',u,note='以官方指數計算與去年同月相比之年增率。')
 u='https://service.moea.gov.tw/EE520/opendata/b.csv';rows=list(csv.DictReader(io.StringIO(get(u).content.decode('utf-8-sig'))));pts=[(month(r['資料期(民國年)']),number(r['統計值(美元)'])) for r in rows if r['統計項目'].strip()=='外銷訂單金額' and number(r['統計值(美元)']) is not None]
 add('tw_orders','外銷訂單金額','億美元','台灣經濟',[(d,v/100) for d,v in pts],'經濟部統計處',u)
 add('tw_orders_yoy','外銷訂單年增率','%','台灣經濟',yoy(pts),'經濟部統計處',u)

def trade():
 page='https://data.gov.tw/dataset/8378';s=soup(page);u=next(a['href'] for a in s.select('a[href]') if a.text.strip()=='CSV');rows=list(csv.reader(io.StringIO(get(u).content.decode('utf-8-sig'))));series=[[],[],[]]
 for r in rows[1:]:
  if not r or not re.search(r'年\s*\d+月',r[0]):continue
  d=month(r[0])
  for i,col in enumerate([2,3,4]):
   v=number(r[col])
   if v is not None:series[i].append((d,v/100))
 for key,title,pts in zip(['tw_exports','tw_imports','tw_balance'],['出口金額','進口金額','貿易順差'],series):add(key,title,'億美元','台灣經濟',pts,'財政部',page,note='出口FOB、進口CIF；原始百萬美元換算為億美元。')

def cbc():
 u='https://cpx.cbc.gov.tw/api/OpenData/FTDOpenData_Day';rows=get(u).json();add('usdtwd','新台幣兌美元','TWD / USD','外匯動向',[(day(r['日期']),r['NTD_USD']) for r in rows],'中央銀行',u,'日','1美元可兌換的新台幣；數值上升表示新台幣貶值。')
 u='https://www.cbc.gov.tw/public/data/OpenData/WebF3.csv';rows=csv.DictReader(io.StringIO(get(u).content.decode('utf-8-sig')));add('tw_reserves','外匯存底','十億美元','台灣經濟',[(month(r['日期']),number(r['金額'])) for r in rows],'中央銀行',u)
 u='https://www.cbc.gov.tw/public/data/OpenData/經研處/EG28D01.csv';rows=list(csv.reader(io.StringIO(get(u).content.decode('utf-8-sig'))));pts=[]
 for r in rows[1:]:
  if len(r)>1:
   try:pts.append((day(r[0]),number(r[1])))
   except (ValueError,IndexError):pass
 add('tw_policy','台灣政策利率','%','利率動向',pts,'中央銀行',u,'日','重貼現率。')
 u='https://www.cbc.gov.tw/tw/lp-641-1.html';s=soup(u);pts=[]
 for tr in s.select('tr'):
  t=tr.get_text(' ',strip=True);m=re.search(r'(\d{4}/\d{2}/\d{2})\s+([\d.]+)',t)
  if m:pts.append((day(m[1]),float(m[2])))
 add('tw_overnight','隔夜拆款利率','%','利率動向',pts,'中央銀行',u,'日','金融業隔夜拆款加權平均利率。')
 u='https://www.cbc.gov.tw/public/data/OpenData/經研處/EG43M01.csv';rows=list(csv.reader(io.StringIO(get(u).content.decode('utf-8-sig'))));pts=[]
 for r in rows[1:]:
  try:
   d=month(r[0]);v=number(r[-1]);pts.append((d,v))
  except (ValueError,IndexError):pass
 add('tw_10y','台灣10年期公債利率','%','利率動向',pts,'中央銀行',u,'月','十年期政府公債次級市場利率（月資料），非盤中報價。')

def taibor():
 u='https://www.ba.org.tw/taiborDaily/index';s=soup(u)
 href=next(a['href'] for a in s.select('a[href]') if '/taiborDaily/DownloadAll' in a['href'])
 z=zipfile.ZipFile(io.BytesIO(get(urljoin(u,href)).content));pts=[]
 for name in z.namelist():
  if '歷史' not in name or not name.endswith('.csv'):continue
  b=z.read(name)
  try:t=b.decode('utf-8-sig')
  except UnicodeDecodeError:t=b.decode('cp950')
  for r in csv.reader(io.StringIO(t)):
   if len(r)>5 and re.fullmatch(r'\d{2}[A-Z]{3}\d{2}',r[0].strip()):
    d=datetime.strptime(r[0].strip(),'%d%b%y').date().isoformat();pts.append((d,number(r[5])))
 add('tw_taibor','3個月TAIBOR','%','利率動向',pts,'中華民國銀行公會',u,'日','銀行公會每日公開檔案；首次取近40個營業日，此後每日累積。')

def bls():
 for code,key,title,unit,transform in [('CUUR0000SA0','us_cpi','美國CPI年增率','%',True),('CUUR0000SA0L1E','us_core','美國核心CPI年增率','%',True),('CES0000000001','us_payroll_total','美國非農就業總人數','千人',False)]:
  u=f'https://api.bls.gov/publicAPI/v1/timeseries/data/{code}?startyear={date.today().year-8}&endyear={date.today().year}';j=get(u).json()
  if j.get('status')!='REQUEST_SUCCEEDED':raise ValueError(str(j.get('message')))
  pts=sorted((f'{p["year"]}-{p["period"][1:]}-01',float(p['value'])) for p in j['Results']['series'][0]['data'] if re.fullmatch(r'M(0[1-9]|1[0-2])',p['period']) and number(p['value']) is not None)
  add(key,title,unit,'美國經濟',yoy(pts) if transform else pts,'美國勞工統計局 BLS',u,note='CPI年增率採未季調指數；非農就業為季調後千人。')
  if key=='us_payroll_total':add('us_payroll','非農就業月增人數','千人','美國經濟',[(pts[i][0],pts[i][1]-pts[i-1][1]) for i in range(1,len(pts)) if int(pts[i][0][:4])*12+int(pts[i][0][5:7])-int(pts[i-1][0][:4])*12-int(pts[i-1][0][5:7])==1],'美國勞工統計局 BLS',u,note='以季調後總人數計算月增；包含官方歷史修正。')

def treasury():
 import xml.etree.ElementTree as ET
 pts2=[];pts10=[];base='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
 for year in range(date.today().year-2,date.today().year+1):
  root=ET.fromstring(get(f'{base}?data=daily_treasury_yield_curve&field_tdr_date_value={year}').content)
  for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
   props=entry.find('.//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties')
   if props is None:continue
   p={x.tag.split('}')[-1]:x.text for x in props};d=p.get('NEW_DATE','')[:10]
   if p.get('BC_2YEAR'):pts2.append((d,float(p['BC_2YEAR'])))
   if p.get('BC_10YEAR'):pts10.append((d,float(p['BC_10YEAR'])))
 add('us_2y','美國2年期公債殖利率','%','美國經濟',pts2,'美國財政部',base,'日','官方每日Par Yield Curve Rates。')
 add('us_10y','美國10年期公債殖利率','%','美國經濟',pts10,'美國財政部',base,'日','官方每日Par Yield Curve Rates。')
 m=dict(pts2);add('us_spread','美債10年－2年利差','百分點','利率動向',[(d,v-m[d]) for d,v in pts10 if d in m],'美國財政部（計算）',base,'日','同日10年期殖利率減2年期殖利率；負值表示倒掛。')

def fred():
 # Official Federal Reserve Bank of St. Louis distribution of BEA/Fed series.
 for code,key,title,unit,note in [('A191RL1Q225SBEA','us_gdp','美國實質GDP季增年率','%','BEA實質GDP季增年率；不能直接與台灣GDP年增率比較。'),('DTWEXBGS','broad_usd','廣義美元指數','指數','聯準會Broad Dollar Index，並非ICE DXY；日觀測值按週發布。'),('DEXJPUS','usdjpy','美元兌日圓','JPY / USD','紐約午間參考匯率，由Fed按週公布，並非東京收盤匯率。'),('DFEDTARU','us_policy','Fed目標利率上限','%','聯邦基金目標利率區間的上限。')]:
  u=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd=2021-01-01';b=get(u).content
  if b[:2]==b'PK':
   z=zipfile.ZipFile(io.BytesIO(b));b=z.read(next(x for x in z.namelist() if x.endswith('.csv')))
  rows=list(csv.reader(io.StringIO(b.decode('utf-8-sig'))));pts=[(r[0],number(r[1])) for r in rows[1:] if len(r)>1]
  add(key,title,unit,'美國經濟' if key=='us_gdp' else '外匯動向' if key in ['usdjpy','broad_usd'] else '利率動向',pts,'BEA／Fed（經FRED）',u,'季' if key=='us_gdp' else '日',note)

def fed_history(kind):
 if kind=='jpy':
  u='https://www.federalreserve.gov/releases/h10/Hist/dat00_ja.htm';key='usdjpy';title='美元兌日圓';unit='JPY / USD';note='紐約午間參考匯率；日觀測值由Fed按週公布，非東京收盤。'
 else:
  u='https://www.federalreserve.gov/releases/h10/summary/jrxwtfb_nb.htm';key='broad_usd';title='廣義美元指數';unit='指數';note='Fed Broad Dollar Index；日觀測值按週公布，並非ICE DXY。'
 sp=soup(u);pts=[]
 for row in sp.select('tr'):
  cells=row.find_all(['td','th']);txt=[c.get_text(' ',strip=True) for c in cells]
  if len(txt)>=2 and re.fullmatch(r'\d{1,2}-[A-Z]{3}-\d{2}',txt[0]) and number(txt[1]) is not None:
   dt=datetime.strptime(txt[0],'%d-%b-%y').date().isoformat();pts.append((dt,number(txt[1])))
 add(key,title,unit,'外匯動向',pts,'美國聯準會 Fed',u,'日',note)

def bea_update():
 u='https://www.bea.gov/data/gdp/gross-domestic-product';sp=soup(u);pts=[]
 for tr in sp.select('tr'):
  txt=tr.get_text(' ',strip=True);m=re.search(r'Q([1-4])\s+(20\d{2}).*?([+−-]?[\d.]+)%',txt)
  if m:pts.append((f'{m[2]}-{(int(m[1])-1)*3+1:02d}-01',float(m[3].replace('−','-'))))
 add('us_gdp','美國實質GDP季增年率','%','美國經濟',pts,'美國經濟分析局 BEA',u,'季','BEA實質GDP季增年率；與台灣年增率不同口徑。近期數據直接從BEA官方更新；初始歷史經FRED取得。')

def twse():
 u='https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST';rows=get(u).json();add('tw_stock','台灣加權指數','點','台灣經濟',[(day(r['Date']),number(r['ClosingIndex'])) for r in rows],'臺灣證券交易所',u,'日','官方最新月份每日收盤；自動累積歷史。')

def announcements():
 import xml.etree.ElementTree as ET
 from email.utils import parsedate_to_datetime
 news=[]
 u='https://www.cbc.gov.tw/tw/lp-302-1.html'
 try:
  sp=soup(u)
  for a in sp.select('a[href]'):
   if 'cp-302-' not in a['href']:continue
   txt=a.parent.get_text(' ',strip=True);m=re.search(r'20\d{2}[-/]\d{2}[-/]\d{2}',txt)
   if m:
    title=a.get_text(' ',strip=True);title=re.sub(r'^\d+\s+','',title);title=title.replace(m[0],'').strip()
    news.append({'date':day(m[0]),'title':title,'source':'中央銀行','region':'台灣','url':urljoin(u,a['href'])})
 except Exception as e:DATA['sources'].append({'name':'央行新聞','status':'error','checkedAt':NOW,'message':str(e)[:160]})
 u='https://www.federalreserve.gov/feeds/press_monetary.xml'
 try:
  root=ET.fromstring(get(u).content)
  for item in root.findall('.//item')[:8]:
   title=item.findtext('title');link=item.findtext('link');pub=item.findtext('pubDate')
   if title and link and pub:
    dt=parsedate_to_datetime(pub).date().isoformat()
    if dt<=TODAY:news.append({'date':dt,'title':title,'source':'Federal Reserve','region':'美國','url':link})
 except Exception as e:DATA['sources'].append({'name':'Fed新聞','status':'error','checkedAt':NOW,'message':str(e)[:160]})
 return news

def calendar():
 # Extract announced future dates from official release pages; never estimate dates.
 out=[]
 for u,title,src in [('https://www.bls.gov/cpi/','美國CPI','BLS'),('https://www.bls.gov/news.release/empsit.toc.htm','美國非農就業','BLS'),('https://www.bea.gov/data/gdp/gross-domestic-product','美國GDP','BEA')]:
  s=soup(u);t=s.get_text(' ',strip=True)
  for pattern in [r'(?:Next release:|Next Release|scheduled to be released on|scheduled to be released)\s*([A-Za-z]+\s+\d{1,2},\s*20\d{2})']:
   m=re.search(pattern,t,re.I)
   if m:
    try:d=datetime.strptime(m[1],'%B %d, %Y').date().isoformat()
    except ValueError:continue
    if d>=TODAY:out.append({'date':d,'title':title,'source':src,'url':u,'note':'依官方預告；時間與異動請見原文'})
 DATA['calendar']=out

JOBS=[('主計總處／GDP',dgbas),('國發會景氣燈號',ndc),('經濟部',moea),('財政部進出口',trade),('中央銀行',cbc),('TAIBOR銀行公會',taibor),('BLS物價與就業',bls),('美國財政部',treasury),('美國GDP BEA',bea_update),('Fed日圓匯率',lambda:fed_history('jpy')),('Fed廣義美元指數',lambda:fed_history('broad')),('臺灣證交所',twse),('官方新聞',announcements),('發布日曆',calendar)]
news=[]
with cf.ThreadPoolExecutor(max_workers=8) as pool:
 futures={pool.submit(fn):name for name,fn in JOBS}
 for f in cf.as_completed(futures):
  name=futures[f]
  try:
   result=f.result();DATA['sources'].append({'name':name,'status':'ok','checkedAt':NOW})
   if isinstance(result,list):news.extend(result)
   print('OK',name,flush=True)
  except Exception as e:
   DATA['sources'].append({'name':name,'status':'error','checkedAt':NOW,'message':str(e)[:180]});print('ERROR',name,str(e)[:180],flush=True)
if news:
 merged={x['url']:x for x in OLD.get('news',[])};merged.update({x['url']:x for x in news if x.get('url','').startswith('http')});DATA['news']=sorted(merged.values(),key=lambda x:x['date'],reverse=True)[:40]
if not DATA.get('cpiCategories') and OLD.get('cpiCategories'):DATA['cpiCategories']=OLD['cpiCategories']
# Cross rate computed only from observations on the same date. Source fixing times differ.
if 'usdtwd' in DATA['series'] and 'usdjpy' in DATA['series']:
 a=dict(DATA['series']['usdtwd']['points']);b=dict(DATA['series']['usdjpy']['points']);pts=[(d,b[d]/v) for d,v in a.items() if d in b and v]
 if pts:add('twdjpy','新台幣兌日圓','JPY / TWD','外匯動向',pts,'央行＋Fed（交叉計算）','https://data.gov.tw/dataset/7232','日','1新台幣可兌換日圓＝USD/JPY ÷ USD/TWD。同日資料但報價時點不同，為參考交叉匯率。')
OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(DATA,ensure_ascii=False,separators=(',',':')));tmp.replace(OUT)
print('Saved',len(DATA['series']),'series;',len(DATA['news']),'news')
# Fail only if no usable official data at all; source errors remain visible in UI and Actions.
if not DATA['series']:sys.exit(1)
