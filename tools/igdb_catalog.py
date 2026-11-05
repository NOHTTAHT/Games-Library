# igdb_catalog.py <build.py out dir (Wikipedia docs)> <out_dir> [existing catalog dir, to keep c/s image ids]
# Builds the "igdb-<plat>-<year>" catalog docs: PS5 / Switch / Switch 2 releases known to IGDB that the
# Wikipedia lists miss. PS5: all years since launch; Switch 1/2: 2024-2027. Needs TWITCH_CLIENT_ID/SECRET.
import json,os,sys,time,re,unicodedata,datetime,collections,glob,urllib.request
W,O=map(os.path.abspath,sys.argv[1:3]); os.makedirs(O,exist_ok=True)
E=os.path.abspath(sys.argv[3]) if len(sys.argv)>3 else None
CID=os.environ["TWITCH_CLIENT_ID"]; SEC=os.environ["TWITCH_CLIENT_SECRET"]
tok=json.load(urllib.request.urlopen(urllib.request.Request(f"https://id.twitch.tv/oauth2/token?client_id={CID}&client_secret={SEC}&grant_type=client_credentials",method="POST")))["access_token"]
def q(body):
    for t in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request("https://api.igdb.com/v4/release_dates",data=body.encode(),headers={"Client-ID":CID,"Authorization":"Bearer "+tok},method="POST"),timeout=60))
        except Exception: time.sleep(2*(t+1))
    return None
def norm(s):
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower(); return re.sub(r"[^a-z0-9]+"," ",s).strip()
def base(s): return re.sub(r"\b(nintendo switch 2 edition|switch 2 edition)\b","",norm(s)).strip()
have=set()
for f in glob.glob(W+"/*.json"):
    if os.path.basename(f) in ("plan.json",) or os.path.basename(f).startswith("igdb-"): continue
    for x in json.load(open(f)).get("items",[]): have.add((base(x["t"]),x["p"][0]))
ed=re.compile(r"(edition|bundle|pack|collection|soundtrack|season pass|upgrade|dlc|demo|version)\b",re.I)
best={}; ok=True
for plat,pid in [("PS5",167),("NS1",130),("NS2",508)]:
    off=0
    while True:
        r=q(f"fields date,game.id,game.name,game.involved_companies.company.name,game.involved_companies.developer,game.involved_companies.publisher,game.genres.name; where platform={pid} & date!=null & date_format=0 & game.game_type=0; sort id asc; limit 500; offset {off};")
        if r is None: ok=False; break
        if not r: break
        for x in r:
            g=x.get("game") or {}
            if not g.get("name"): continue
            d=datetime.datetime.fromtimestamp(x["date"],datetime.timezone.utc).date().isoformat(); k=(g["id"],plat)
            if k not in best or d<best[k][0]: best[k]=(d,g)
        off+=500; time.sleep(0.3)
if not ok: print("IGDB_FAILED"); sys.exit(1)
keep={}
if E:
    for f in glob.glob(E+"/**/igdb-*.json",recursive=True):
        for x in json.load(open(f)).get("items",[]):
            if x.get("c"): keep[(base(x["t"]),x["p"][0])]={k:x[k] for k in ("c",) if x.get(k)}
extra=collections.defaultdict(list); seen=set()
for (gid,plat),(d,g) in best.items():
    y=d[:4]; t=g["name"]
    if plat=="PS5" and d<"2020-11-12": continue
    if plat!="PS5" and not ("2024"<=y<="2027"): continue
    if (ed.search(t) and " - " in t) or re.search(r"(deluxe|digital|ultimate|gold|complete|premium) edition",t,re.I): continue
    if (base(t),plat) in have or (base(t),plat) in seen: continue
    ic=g.get("involved_companies") or []
    dev=", ".join(c["company"]["name"] for c in ic if c.get("developer") and c.get("company"))[:120]
    pub=", ".join(c["company"]["name"] for c in ic if c.get("publisher") and c.get("company"))[:120]
    if not (dev or pub): continue
    seen.add((base(t),plat)); gen=", ".join(x["name"] for x in g.get("genres") or [])[:80]
    it={"d":d,"t":t,"p":[plat]}
    if dev: it["dev"]=dev
    if pub: it["pub"]=pub
    if gen: it["g"]=gen
    it.update(keep.get((base(t),plat),{}))
    extra[f"igdb-{plat.lower()}-{y}"].append(it)
ids=[]
for doc,its in extra.items():
    its.sort(key=lambda i:(i["d"],i["t"])); chunks=[its]
    while any(len(json.dumps({"items":c},ensure_ascii=False).encode())>240000 for c in chunks):
        chunks=[h for c in chunks for h in (c[:len(c)//2],c[len(c)//2:])]
    names=[doc] if len(chunks)==1 else [doc+chr(97+i) for i in range(len(chunks))]
    for nm,c in zip(names,chunks): json.dump({"items":c},open(f"{O}/{nm}.json","w"),ensure_ascii=False); ids.append(nm)
print(json.dumps({"docs":sorted(ids),"items":sum(len(v) for v in extra.values())}))
