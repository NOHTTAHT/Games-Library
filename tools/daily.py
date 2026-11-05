# Daily update (GitHub Actions, 12:00 Bangkok): release calendar (Wikipedia + IGDB), missing covers (IGDB), Top 10 (IGDB).
# Env: SUPABASE_URL, SUPABASE_SECRET_KEY, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
import datetime, glob, json, os, re, shutil, subprocess, sys, time, unicodedata, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import supa

W = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/tmp/daily")
shutil.rmtree(W, ignore_errors=True); os.makedirs(W)
PY = sys.executable
TODAY = datetime.date.today().isoformat()
report = []

def run(*args):
    r = subprocess.run([PY, *args], capture_output=True, text=True)
    print(r.stdout[-3000:], r.stderr[-3000:], flush=True)
    return r

# ---------- 1) release calendar ----------
existing = supa.list_docs("catalog")
ex_dir = f"{W}/existing/catalog"; os.makedirs(ex_dir)
for k, v in existing.items():
    json.dump(v, open(f"{ex_dir}/{k}.json", "w"), ensure_ascii=False)
print("existing catalog docs:", len(existing), flush=True)

out, igd = f"{W}/out", f"{W}/igdb"
wiki_ok = "ALL_OK" in run(f"{HERE}/fetch.py", f"{W}/html").stdout
new_docs, deletes = {}, set()
if wiki_ok:
    r = run(f"{HERE}/build.py", f"{W}/html", f"{W}/existing", out)
    wiki_ok = r.returncode == 0 and os.path.exists(f"{out}/plan.json")
if wiki_ok:
    plan = json.load(open(f"{out}/plan.json"))
    for k in plan["set"]:
        new_docs[k] = json.load(open(f"{out}/{k}.json"))
    deletes |= set(plan["delete"])
    report.append(f"Wikipedia: +{plan['added']} changed {plan['changed']} removed {len(plan['removed'])}" + ("" if plan["safe"] else " (kept vanished games)"))
else:
    os.makedirs(out, exist_ok=True)  # let IGDB step see what the calendar already has
    for k, v in existing.items():
        if not k.startswith("igdb-"):
            json.dump(v, open(f"{out}/{k}.json", "w"), ensure_ascii=False)
    report.append("Wikipedia: failed, kept existing lists")

r = run(f"{HERE}/igdb_catalog.py", out, igd, f"{W}/existing")
if "IGDB_FAILED" in r.stdout or r.returncode:
    report.append("IGDB calendar: failed, kept existing")
else:
    made = set()
    for f in glob.glob(f"{igd}/*.json"):
        k = os.path.basename(f)[:-5]; made.add(k); new_docs[k] = json.load(open(f))
    deletes |= {k for k in existing if k.startswith("igdb-") and k not in made}

changed = {k: v for k, v in new_docs.items() if existing.get(k) != v}
if changed:
    supa.set_docs("catalog", changed)
for k in deletes:
    if k in existing and k not in new_docs:
        supa.delete_doc("catalog", k)
report.append(f"calendar docs written {len(changed)}, deleted {len([k for k in deletes if k in existing and k not in new_docs])}")

# ---------- 2) missing covers from IGDB ----------
CID, SEC = os.environ["TWITCH_CLIENT_ID"], os.environ["TWITCH_CLIENT_SECRET"]
tok = json.load(urllib.request.urlopen(urllib.request.Request(
    f"https://id.twitch.tv/oauth2/token?client_id={CID}&client_secret={SEC}&grant_type=client_credentials", method="POST")))["access_token"]

def igdb(body):
    for t in range(4):
        try:
            time.sleep(0.28)
            req = urllib.request.Request("https://api.igdb.com/v4/games", data=body.encode(),
                                         headers={"Client-ID": CID, "Authorization": "Bearer " + tok}, method="POST")
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 * (t + 1)); continue
            return None
        except Exception:
            time.sleep(3)
    return None

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(nintendo switch 2 edition|switch 2 edition|nintendo switch edition|ps5 edition|director'?s cut|remastered|deluxe edition|complete edition)\b", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def app_norm(s):  # same as norm() in the page
    s = str(s or "").lower()
    s = re.sub(r"[™®©:'’\-–—.,!&+]", " ", s)
    s = re.sub(r"nintendo switch 2 edition|switch 2 edition", "", s)
    return re.sub(r"\s+", " ", s).strip()

def info_key(t):
    k = re.sub(r"[^a-z0-9]+", "-", app_norm(t)).strip("-")[:120]
    if k: return k
    h = 0
    for c in str(t): h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return "t" + format(h, "x")

def find_cover(title):
    term = re.sub(r'["\\]', "", re.sub(r"\s*[–—-]?\s*(Nintendo Switch 2 Edition|Switch 2 Edition)\s*$", "", title))
    hits = igdb(f'search "{term}"; fields name,alternative_names.name,cover.image_id; limit 10;')
    if hits is None: return None
    key = norm(title)
    for h in hits:
        names = [h.get("name", "")] + [a.get("name", "") for a in h.get("alternative_names") or []]
        if any(norm(x) == key for x in names) and h.get("cover"):
            return "ig:" + h["cover"]["image_id"]
    return ""

state = supa.get_doc("meta", "coverfill") or {"tried": {}}
tried = state.get("tried", {})
retry_before = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
cat = supa.list_docs("catalog")
games = supa.list_docs("games"); info = supa.list_docs("gameinfo")
have_cover = {app_norm(x["t"]) for d in cat.values() for x in d.get("items", []) if x.get("c")}
LIMIT = 900; done = 0; found = 0
# a) the owner's games first
info_patch = {}
for gid, g in games.items():
    t = g.get("title") or ""; k = info_key(t)
    if not t or g.get("coverId") or (info.get(k) or {}).get("coverId") or app_norm(t) in have_cover: continue
    if tried.get("g:" + k, "") > retry_before or done >= LIMIT: continue
    c = find_cover(t); done += 1
    if c is None: continue
    tried["g:" + k] = TODAY
    if c:
        found += 1; d = dict(info.get(k) or {}); d.update({"title": t, "coverId": c, "updatedAt": TODAY}); info_patch[k] = d
if info_patch: supa.set_docs("gameinfo", info_patch)
# b) the release calendar, newest years first
cat_patch = {}
for doc_id in sorted(cat, key=lambda k: re.sub(r"\D", "", k)[:4], reverse=True):
    items = cat[doc_id].get("items", []); ch = False
    for x in items:
        if done >= LIMIT: break
        if x.get("c") or not x.get("t"): continue
        k = "c:" + app_norm(x["t"]) + "|" + x["p"][0]
        if tried.get(k, "") > retry_before: continue
        c = find_cover(x["t"]); done += 1
        if c is None: continue
        tried[k] = TODAY
        if c: x["c"] = c; ch = True; found += 1
    if ch: cat_patch[doc_id] = cat[doc_id]
if cat_patch: supa.set_docs("catalog", cat_patch)
supa.set_docs("meta", {"coverfill": {"tried": tried, "updatedAt": TODAY}})
report.append(f"covers: looked up {done}, found {found}")

# ---------- 3) Top 10 ----------
r = run(f"{HERE}/top10.py", f"{W}/top10.json")
if r.returncode == 0 and os.path.exists(f"{W}/top10.json"):
    t10 = json.load(open(f"{W}/top10.json"))
    if any(v["hot"] or v["rated"] for v in t10["lists"].values()):
        supa.set_docs("meta", {"top10": t10}); report.append("top10: updated")
else:
    report.append("top10: failed, kept existing")

# ---------- 4) calendar stamp ----------
rel = supa.get_doc("meta", "releases") or {"items": []}
rel.update({"updatedAt": TODAY, "source": "Wikipedia + IGDB"})
supa.set_docs("meta", {"releases": rel})

print("\n".join(report))
with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as f:
    f.write("## Daily update\n\n" + "\n".join("- " + x for x in report) + "\n")
