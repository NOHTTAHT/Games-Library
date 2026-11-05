# top10.py <out.json>
# Weekly "Top 10" per console for the Games Library app (doc meta/top10).
# Source: IGDB (needs env TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET).
#  hot   = new games (first released in the last 365 days), ranked by IGDB popularity now (Visits + Playing + Want to Play, rank-blended)
#  rated = new games (first released in the last 365 days), ranked by critic score (aggregated_rating, >= 3 critic reviews)
import json,os,sys,time,datetime,urllib.request
CID=os.environ["TWITCH_CLIENT_ID"]; SEC=os.environ["TWITCH_CLIENT_SECRET"]
tok=json.load(urllib.request.urlopen(urllib.request.Request(f"https://id.twitch.tv/oauth2/token?client_id={CID}&client_secret={SEC}&grant_type=client_credentials",method="POST")))["access_token"]
def ig(ep,body):
    for t in range(4):
        try:
            time.sleep(0.3)
            r=urllib.request.Request("https://api.igdb.com/v4/"+ep,data=body.encode(),headers={"Client-ID":CID,"Authorization":"Bearer "+tok},method="POST")
            return json.load(urllib.request.urlopen(r,timeout=40))
        except Exception: time.sleep(2*(t+1))
    raise SystemExit("IGDB_FAILED "+ep)
PL={"PS5":167,"NS2":508,"NS1":130}
F="fields name,first_release_date,aggregated_rating,aggregated_rating_count,total_rating,genres.name,involved_companies.publisher,involved_companies.developer,involved_companies.company.name,platforms,game_type,release_dates.platform,release_dates.date;"
now=int(time.time()); since=now-365*86400
def plat_date(g,p):
    ds=[r["date"] for r in g.get("release_dates") or [] if r.get("platform")==p and r.get("date")]
    return min(ds) if ds else None
def item(g,p,extra):
    d=plat_date(g,p) or g.get("first_release_date")
    ic=g.get("involved_companies") or []
    pub=next((c["company"]["name"] for c in ic if c.get("publisher") and c.get("company")),"")
    dev=next((c["company"]["name"] for c in ic if c.get("developer") and c.get("company")),"")
    it={"t":g["name"],"id":g["id"],"d":datetime.datetime.fromtimestamp(d,datetime.timezone.utc).strftime("%Y-%m-%d") if d else "",
        "g":", ".join(x["name"] for x in (g.get("genres") or [])[:2]),"pub":pub or dev}
    if g.get("aggregated_rating"): it["score"]=round(g["aggregated_rating"])
    it.update(extra); return it
# popularity: rank-blend three IGDB signals
rank={}
for t in (1,3,2):
    rows=[]
    for off in (0,500,1000,1500):
        rows+=ig("popularity_primitives",f"fields game_id,value; where popularity_type={t}; sort value desc; limit 500; offset {off};")
    for i,r in enumerate(rows): rank.setdefault(r["game_id"],0); rank[r["game_id"]]+=1/(i+20)
ids=sorted(rank); G={}
for i in range(0,len(ids),400):
    for g in ig("games",F+f"where id=({','.join(map(str,ids[i:i+400]))}); limit 500;"): G[g["id"]]=g
OK_TYPES={0,8,9,10,11}  # main game, remake, remaster, expanded game, port
out={"updatedAt":datetime.date.today().isoformat(),"source":"IGDB","lists":{}}
for k,p in PL.items():
    hot=[]
    for gid in sorted(rank,key=lambda x:-rank[x]):
        g=G.get(gid)
        if not g or p not in (g.get("platforms") or []) or g.get("game_type",0) not in OK_TYPES: continue
        d=g.get("first_release_date")
        if not d or d<since or d>now: continue
        hot.append(item(g,p,{}))
        if len(hot)==10: break
    cand=ig("games",F+f"where platforms=({p}) & aggregated_rating_count>=3 & aggregated_rating!=null & game_type=({','.join(map(str,OK_TYPES))}) & first_release_date>={since} & first_release_date<={now}; sort aggregated_rating desc; limit 80;")
    rated=[]
    for g in cand:
        rated.append(item(g,p,{"n":g.get("aggregated_rating_count",0)}))
        if len(rated)==10: break
    out["lists"][k]={"hot":hot,"rated":rated}
json.dump(out,open(sys.argv[1],"w"),ensure_ascii=False,indent=1)
for k,v in out["lists"].items():
    print(k,"HOT:",", ".join(x["t"] for x in v["hot"]))
    print(k,"RATED:",", ".join(f'{x["t"]} {x.get("score")}' for x in v["rated"]))
