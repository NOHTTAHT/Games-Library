# Thai store prices (GitHub Actions, daily): PlayStation Store Thailand (en-th), prices in baht.
# Writes collection "prices" in Supabase:
#   ps-0, ps-1, ...   {items:[{t,b,s?,p?,e?,id,x?}]}  every PS5 game: title, base price, sale price, % off, sale end date, product id
#   sale-0, sale-1 ... {items:[{t,b,s,p,e,st,id,c,x?,pl}]} PS5 games on sale now, with end date and first-seen date
#   meta              {updatedAt, ps:{games,sales}, source}
# Env: SUPABASE_URL, SUPABASE_SECRET_KEY.  Nintendo has no Thai eShop, so Switch prices are not fetched.
import concurrent.futures, datetime, json, os, re, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import supa

GQL = "https://web.np.playstation.com/api/graphql/v1/op"
HEAD = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "x-psn-store-locale-override": "en-TH", "content-type": "application/json"}
HASH_GRID = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"   # categoryGridRetrieve
HASH_CTA = "8532da7eda369efdad054ca8f885394a2d0c22d03c5259a422ae2bb3b98c5c99"    # productRetrieveForCtasWithPrice
CAT_PS5 = "4cbf39e2-5749-4970-ba81-93a489e4570c"    # All PS5 games
CAT_DEALS = "3f772501-f6f8-49b7-abac-874a88ca4897"  # Deals (PS4 + PS5)
GAMES = {"FULL_GAME", "GAME_BUNDLE", "PREMIUM_EDITION"}
BKK = datetime.timezone(datetime.timedelta(hours=7))
TODAY = datetime.datetime.now(BKK).date().isoformat()
DRY = os.environ.get("DRY_RUN") == "1"   # test run: no database, few end-date lookups, prints a sample
STOP_AT = time.time() + (90 if DRY else 45 * 60)   # end-date lookups stop in time to save
CHUNK = {"ps": 1500, "sale": 600}     # items per document (keeps each row under ~200 KB for live updates)
IMG = "https://image.api.playstation.com/vulcan/ap/rnd/"

def gql(op, var, hsh):
    u = GQL + "?" + urllib.parse.urlencode({"operationName": op, "variables": json.dumps(var),
                                            "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": hsh}})})
    for t in range(4):
        try:
            time.sleep(0.12)
            with urllib.request.urlopen(urllib.request.Request(u, headers=HEAD), timeout=90) as r:
                d = json.loads(r.read().decode())
            if d.get("data"): return d["data"]
            print("GQL_ERROR", op, json.dumps(d)[:300], flush=True)
            if "not whitelisted" in json.dumps(d): return None
        except urllib.error.HTTPError as e:
            print("GQL_HTTP", op, e.code, e.read().decode()[:200], flush=True)
            if e.code == 400: return None
        except Exception as e:
            print("GQL_FAIL", op, repr(e), flush=True)
        time.sleep(3 * (t + 1))
    return None

def grid(cat):
    out, off, total = [], 0, None
    while total is None or off < total:
        d = gql("categoryGridRetrieve", {"id": cat, "pageArgs": {"size": 1000, "offset": off}, "sortBy": None, "filterBy": [], "facetOptions": []}, HASH_GRID)
        g = d and d.get("categoryGridRetrieve")
        if not g: return None
        total = (g.get("pageInfo") or {}).get("totalCount") or 0
        ps = g.get("products") or []
        out += ps; off += 1000
        if not ps: break
    print("category", cat, "products", len(out), "of", total, flush=True)
    return out

def money(s):
    s = str(s or "")
    if "THB" not in s: return None
    try: return round(float(re.sub(r"[^\d.]", "", s)), 2)
    except ValueError: return None

def num(v): return int(v) if v == int(v) else v

LANG = r"english|chinese|korean|japanese|thai|ver\.|version|asia|traditional|simplified"
def clean(name):
    n = re.sub(r"[™®©]", "", name or "").strip()
    for _ in range(3):
        n = re.sub(r"\s*[\(\[]([^()\[\]]*)[\)\]]\s*$", lambda m: "" if re.search(LANG + r"|ps4|ps5", m.group(1), re.I) else m.group(0), n).strip()
        n = re.sub(r"\s*[-–:]?\s*(ps4\s*(&|and)\s*ps5|ps5\s*(&|and)\s*ps4|ps5|ps4)$", "", n, flags=re.I).strip()
        n = re.sub(r"\s*[-–]\s*$", "", n)
        n = re.sub(r"\s+standard edition$", "", n, flags=re.I)
    return n or (name or "").strip()

def cover(p):
    by = {m.get("role"): m.get("url", "") for m in p.get("media") or [] if m.get("type") == "IMAGE"}
    u = by.get("MASTER") or by.get("GAMEHUB_COVER_ART") or by.get("EDITION_KEY_ART") or by.get("PORTRAIT_BANNER") or ""
    return u[len(IMG):] if u.startswith(IMG) else ""

def plus_only(pr):
    return bool(pr.get("isExclusive")) or "PS_PLUS" in (pr.get("serviceBranding") or [])

def item(p):
    pr = p.get("price") or {}
    b, s = money(pr.get("basePrice")), money(pr.get("discountedPrice"))
    if b is None: return None
    it = {"t": clean(p.get("name")), "b": num(b), "id": p.get("id")}
    m = re.search(r"(\d+)", pr.get("discountText") or "")
    if m and s is not None and s < b:
        it.update({"s": num(s), "p": int(m.group(1))})
        if plus_only(pr): it["x"] = 1   # PS Plus members only
    return it

def end_date(pid, want):
    """Sale end date (Bangkok) for a product, from its buy button price."""
    d = gql("productRetrieveForCtasWithPrice", {"productId": pid}, HASH_CTA)
    ctas = ((d or {}).get("productRetrieve") or {}).get("webctas") or []
    best = None
    for c in ctas:
        pr = c.get("price") or {}
        et = pr.get("endTime")
        if not et or not str(et).isdigit(): continue
        ds = datetime.datetime.fromtimestamp(int(et) / 1000, BKK).date().isoformat()
        if money(pr.get("discountedPrice")) == want: return ds
        best = best or ds
    return best if d else None   # None = lookup failed, "" = no end date

def chunks(prefix, items):
    n = CHUNK[prefix]
    return {f"{prefix}-{i // n}": {"items": items[i:i + n]} for i in range(0, len(items), n)}

def main():
    report = []
    allp = grid(CAT_PS5)
    deals = grid(CAT_DEALS)
    if not allp:
        print("PS_FAILED"); report.append("PS Store: failed, kept existing prices"); return report
    # 1) one price per title: prefer the standard full game, else the cheapest edition
    best = {}
    for p in allp:
        if p.get("storeDisplayClassification") not in GAMES: continue
        it = item(p)
        if not it: continue
        rank = (p.get("storeDisplayClassification") != "FULL_GAME", it["b"])
        k = it["t"].lower()
        if k not in best or rank < best[k][0]: best[k] = (rank, it)
    games = {k: v[1] for k, v in best.items()}
    # 2) games on sale (PS5), with end date (looked up once per sale) and the day we first saw the sale
    state = ({} if DRY else supa.get_doc("prices", "state")) or {"sales": {}}
    seen = state.get("sales", {})
    sales, looked, failed, live = [], 0, 0, set()
    src = [p for p in (deals or []) if "PS5" in (p.get("platforms") or []) and p.get("storeDisplayClassification") in GAMES]
    src += [p for p in allp if (p.get("price") or {}).get("discountText") and p.get("storeDisplayClassification") in GAMES]
    done, cur = set(), []
    for p in src:
        if p.get("id") in done: continue
        done.add(p.get("id"))
        it = item(p)
        if not it or "s" not in it: continue
        key = f"{it['s']}|{it['p']}"
        st = seen.get(it["id"])
        if not st or st.get("k") != key:
            st = {"k": key, "st": TODAY, "e": None}
        seen[it["id"]] = st; live.add(it["id"])
        cur.append((p, it, st))
    todo = [(it, st) for p, it, st in cur if st.get("e") is None]
    def look(x):
        it, st = x
        if time.time() > STOP_AT: return x, None
        return x, end_date(it["id"], it["s"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for (it, st), e in ex.map(look, todo):
            if time.time() <= STOP_AT: looked += 1
            if e is None: failed += 1
            else: st["e"] = e
    for p, it, st in cur:
        if st.get("e") and st["e"] < TODAY: continue   # already over
        it.update({"e": st.get("e") or "", "st": st["st"], "c": cover(p), "pl": [x for x in p.get("platforms") or [] if x in ("PS4", "PS5")]})
        sales.append(it)
        g = games.get(it["t"].lower())
        if g and g.get("id") == it["id"]: g.update({k: it[k] for k in ("s", "p", "e", "x") if k in it})
    seen = {k: v for k, v in seen.items() if k in live}
    sales.sort(key=lambda x: (-x["p"], x["t"].lower()))
    glist = sorted(games.values(), key=lambda x: x["t"].lower())
    for it in glist:
        if "s" in it and "e" not in it:
            st = seen.get(it["id"]); it["e"] = (st or {}).get("e") or ""
    # 3) save: replace chunk docs, remove leftovers
    docs = {**chunks("ps", glist), **chunks("sale", sales)}
    docs["meta"] = {"updatedAt": TODAY, "source": "PlayStation Store Thailand", "ps": {"games": len(glist), "sales": len(sales)}}
    if DRY:
        print("SAMPLE games", json.dumps(glist[:5], ensure_ascii=False))
        print("SAMPLE sales", json.dumps(sales[:8], ensure_ascii=False))
        for t in ["astro bot", "marvel’s spider-man 2", "ghost of yōtei", "stellar blade", "elden ring", "ea sports fc 27"]:
            print("LOOKUP", t, json.dumps(games.get(t), ensure_ascii=False))
        print("SIZES", {k: len(json.dumps(v, ensure_ascii=False)) for k, v in docs.items()})
        return [f"DRY RUN: {len(glist)} games, {len(sales)} sales, end dates looked up {looked} (failed {failed})"]
    old = supa.list_ids("prices")
    supa.set_docs("prices", docs)
    supa.set_docs("prices", {"state": {"sales": seen, "updatedAt": TODAY}})
    for k in old:
        if re.match(r"(ps|sale)-\d+$", k) and k not in docs: supa.delete_doc("prices", k)
    report.append(f"PS Store TH: {len(glist)} games priced, {len(sales)} PS5 games on sale, end dates looked up {looked} (failed {failed})")
    return report

if __name__ == "__main__":
    rep = main()
    print("\n".join(rep))
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as f:
        f.write("## Thai store prices\n\n" + "\n".join("- " + x for x in rep) + "\n")
