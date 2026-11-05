# Download the Wikipedia list pages (rendered HTML) into <outdir>. Slow on purpose: Wikipedia rate-limits hard.
import sys,os,time,urllib.request,urllib.parse
UA="GamesLibraryBot/1.0 (personal non-commercial project)"
PAGES={"PS5":["List_of_PlayStation_5_games"],"NS2":["List_of_Nintendo_Switch_2_games"],
 "NS1":["List_of_Nintendo_Switch_games_(0–9)","List_of_Nintendo_Switch_games_(A–Am)","List_of_Nintendo_Switch_games_(An–Az)","List_of_Nintendo_Switch_games_(B)","List_of_Nintendo_Switch_games_(C–G)","List_of_Nintendo_Switch_games_(H–P)","List_of_Nintendo_Switch_games_(Q–Z)"]}
out=sys.argv[1]; os.makedirs(out,exist_ok=True); ok=True
for plat,ps in PAGES.items():
    for i,p in enumerate(ps):
        f=f"{out}/{plat}_{i}.html"
        for t in range(8):
            time.sleep(5+t*15)
            try:
                b=urllib.request.urlopen(urllib.request.Request("https://en.wikipedia.org/api/rest_v1/page/html/"+urllib.parse.quote(p),headers={"User-Agent":UA}),timeout=90).read()
                if len(b)>50000: open(f,"wb").write(b); break
            except Exception as e: print("retry",p,e,flush=True)
        else: print("FAILED",p); ok=False
print("ALL_OK" if ok else "SOME_FAILED")
