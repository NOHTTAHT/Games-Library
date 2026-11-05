# build.py <html_dir> <existing_catalog_dir> <out_dir>
# Parses fresh lists, keeps c/s (cover/screenshot asset ids) from existing catalog docs,
# writes one JSON per doc to out_dir, plus plan.json {set:[doc_ids], delete:[doc_ids], removed:[titles], added:n, changed:n, safe:bool}
import sys,json,glob,os,re,subprocess,collections
H,E,O=map(os.path.abspath,sys.argv[1:4]); os.makedirs(O,exist_ok=True); here=os.path.dirname(os.path.abspath(__file__))
def norm(s): return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()
new=[]
for plat in ["PS5","NS1","NS2"]:
    files=sorted(glob.glob(f"{H}/{plat}_*.html"))
    subprocess.run([sys.executable,"-I",f"{here}/parse.py",plat,*files],cwd=O,check=True,stdout=subprocess.DEVNULL)
    new+=json.load(open(f"{O}/out_{plat}.json")); os.remove(f"{O}/out_{plat}.json")
old=[]; oldids=set()
for f in glob.glob(f"{E}/**/*.json",recursive=True):
    if not re.match(r"^(ps5|ns1|ns2)-\d{4}[a-z]?\.json$",os.path.basename(f)): continue  # only Wikipedia docs are managed here (igdb-*, ps4-notable etc. are left alone)
    d=json.load(open(f)); oldids.add(os.path.basename(f)[:-5])
    old+= (d.get("data",d).get("items") or [])
key=lambda x:(norm(x["t"]),x["p"][0])
om={key(x):x for x in old}
nm={}
for x in new:
    it={k:x[k] for k in ["d","t","p","dev","pub","g"] if x.get(k)}
    o=om.get(key(it))
    if o:
        for k in ["c"]+([] if it.get("g") else ["g"]):
            if o.get(k): it[k]=o[k]
    nm[key(it)]=it
removed=[om[k]["t"]+" ("+k[1]+")" for k in om if k not in nm]
added=sum(1 for k in nm if k not in om)
changed=sum(1 for k in nm if k in om and any(nm[k].get(f)!=om[k].get(f) for f in ["d","dev","pub","g"]))
perplat_old=collections.Counter(k[1] for k in om); perplat_new=collections.Counter(k[1] for k in nm)
safe=all(perplat_new[p]>=0.95*perplat_old[p] for p in perplat_old) and len(nm)>0
items=list(nm.values())
if not safe:  # keep games that vanished, only update/add
    for k in om:
        if k not in nm: items.append(om[k])
    removed=[]
pre={"PS5":"ps5","NS1":"ns1","NS2":"ns2"}; g=collections.defaultdict(list)
for it in items: g[f'{pre[it["p"][0]]}-{it["d"][:4]}'].append(it)
ids=[]
for doc,its in g.items():
    its.sort(key=lambda i:(i["d"],i["t"]))
    # split if near the 256 KiB limit
    chunks=[its]; 
    while any(len(json.dumps({"items":c},ensure_ascii=False).encode())>240000 for c in chunks):
        chunks=[h for c in chunks for h in (c[:len(c)//2],c[len(c)//2:])]
    names=[doc] if len(chunks)==1 else [doc+chr(97+i) for i in range(len(chunks))]
    for n,c in zip(names,chunks):
        json.dump({"items":c},open(f"{O}/{n}.json","w"),ensure_ascii=False); ids.append(n)
plan={"set":sorted(ids),"delete":sorted(oldids-set(ids)),"removed":removed,"added":added,"changed":changed,"safe":safe,"counts":dict(perplat_new)}
json.dump(plan,open(f"{O}/plan.json","w"),ensure_ascii=False,indent=1)
print(json.dumps({k:(v if k!="removed" else v[:50]) for k,v in plan.items()},ensure_ascii=False))
