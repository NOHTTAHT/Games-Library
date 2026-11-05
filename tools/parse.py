import sys, json, re, datetime
from bs4 import BeautifulSoup
MON={m:i for i,m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"],1)}
def pdate(s):
    s=re.sub(r'\[.*?\]','',s).strip()
    m=re.search(r'([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})',s)
    if m and m.group(1).lower() in MON:
        try: return datetime.date(int(m.group(3)),MON[m.group(1).lower()],int(m.group(2))).isoformat()
        except: return None
    m=re.search(r'(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})',s)
    if m and m.group(2).lower() in MON:
        try: return datetime.date(int(m.group(3)),MON[m.group(2).lower()],int(m.group(1))).isoformat()
        except: return None
    return None
def clean(c):
    for x in c.select('sup, style, .reference, link'): x.decompose()
    # list items -> comma
    for li in c.find_all('li'): li.insert_after(', ')
    for br in c.find_all('br'): br.replace_with(', ')
    t=c.get_text(' ',strip=True)
    t=re.sub(r'\s+',' ',t); t=re.sub(r'\s*,\s*(,\s*)*',', ',t).strip(' ,')
    t=re.sub(r'\s+([,:])',r'\1',t)
    return t
def grid(table):
    rows=table.find_all('tr'); out=[]; pend={}
    for r in rows:
        cells=r.find_all(['th','td'],recursive=False); row=[]; ci=0; it=iter(cells)
        while True:
            if ci in pend:
                cell,left=pend[ci]; row.append(cell)
                if left>1: pend[ci]=(cell,left-1)
                else: del pend[ci]
                ci+=1; continue
            c=next(it,None)
            if c is None:
                # flush remaining pend beyond
                while ci in pend:
                    cell,left=pend[ci]; row.append(cell)
                    if left>1: pend[ci]=(cell,left-1)
                    else: del pend[ci]
                    ci+=1
                break
            rs=int(re.sub(r'\D','',c.get('rowspan','1')) or 1); cs=int(re.sub(r'\D','',c.get('colspan','1')) or 1)
            for k in range(cs):
                row.append(c)
                if rs>1: pend[ci]=(c,rs-1)
                ci+=1
        out.append(row)
    return out
plat=sys.argv[1]; res=[]
for f in sys.argv[2:]:
    s=BeautifulSoup(open(f,encoding='utf8'),'lxml')
    t=s.find('table',id='softwarelist') or max(s.select('table.wikitable'),key=lambda t:len(t.find_all('tr')))
    g=grid(t)
    hdr=[c.get_text(' ',strip=True) for c in g[0]]
    ti=0; di=hdr.index('Developer(s)'); pi=hdr.index('Publisher(s)'); gi=hdr.index('Genre(s)') if 'Genre(s)' in hdr else None
    dcols=[i for i,h in enumerate(hdr) if h.startswith('Release date')]
    start=1
    if plat=='PS5': start=2
    for row in g[start:]:
        if len(row)<=max(dcols+[pi]): continue
        tc=row[0]
        a=tc.find('a',href=True); art=None
        if a and tc.find('i') and a.get('href','').startswith('./'): art=a['href'][2:]
        title=clean(BeautifulSoup(str(tc),'lxml'))
        dates=[pdate(BeautifulSoup(str(row[i]),'lxml').get_text(' ',strip=True)) for i in dcols]
        dates=[d for d in dates if d]
        if not dates or not title: continue
        dev=clean(BeautifulSoup(str(row[di]),'lxml')); pub=clean(BeautifulSoup(str(row[pi]),'lxml'))
        g=clean(BeautifulSoup(str(row[gi]),'lxml'))[:80] if gi is not None else ''
        res.append(dict(d=min(dates),t=title,p=[plat],dev=dev[:120],pub=pub[:120],g=g,art=art))
json.dump(res,open(f'out_{plat}.json','w'),ensure_ascii=False)
print(plat,len(res)); import collections; print(sorted(collections.Counter(r['d'][:4] for r in res).items()))
for r in res[:3]+res[-3:]: print(r)
