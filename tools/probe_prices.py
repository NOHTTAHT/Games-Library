# Temporary probe round 3
import json, re, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-TH,en;q=0.9"}
def get(u, h=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={**UA, **(h or {})}), timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, repr(e)
G = "https://web.np.playstation.com/api/graphql/v1/op"
HD = {"x-psn-store-locale-override": "en-TH", "content-type": "application/json"}
def gql(op, var, hsh):
    u = G + "?" + urllib.parse.urlencode({"operationName": op, "variables": json.dumps(var), "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": hsh}})})
    return get(u, HD)
CG = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"
s, h = gql("metGetPricingDataByConceptId", {"conceptId": "10002456"}, "abcb311ea830e679fe2b697a27f755764535d825b24510ab1239a4ca3092bd09")
d = json.loads(h); 
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in ("mobilectas", "param", "__typename")}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
print("== pricing", json.dumps(strip(d))[:2500])
s, h = get("https://store.playstation.com/en-th/pages/deals")
ids = sorted(set(re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', h)))
print("== deals uuids", len(ids), re.findall(r'href="(/en-th/[^"]+)"', h)[:40])
cands = ids + ["4cbf39e2-5749-4970-ba81-93a489e4570c", "d0446d4b-dc9a-4f1e-86ec-651f099c9b29", "3f772501-f6f8-49b7-abac-874a88ca4897", "803cee19-e5a1-4d59-a463-0b6b2701bf7c"]
for c in cands:
    s, h = gql("categoryGridRetrieve", {"id": c, "pageArgs": {"size": 3, "offset": 0}, "sortBy": None, "filterBy": [], "facetOptions": []}, CG)
    try:
        g = json.loads(h)["data"]["categoryGridRetrieve"]
    except Exception:
        g = None
    if g:
        print("== cat", c, g.get("name"), "total", (g.get("pageInfo") or {}).get("totalCount"))
        for p in g.get("products", [])[:2]:
            print("   ", json.dumps(strip(p))[:900])
    else:
        print("   cat", c, s, h[:120])
# big page size
s, h = gql("categoryGridRetrieve", {"id": "4cbf39e2-5749-4970-ba81-93a489e4570c", "pageArgs": {"size": 1000, "offset": 0}, "sortBy": None, "filterBy": [], "facetOptions": []}, CG)
try: print("== size1000", len(json.loads(h)["data"]["categoryGridRetrieve"]["products"]), len(h))
except Exception as e: print("== size1000 fail", s, h[:200])
# Nintendo ec search endpoints
for u in ["https://ec.nintendo.com/api/HK/zh/search/sales?count=5&offset=0",
          "https://ec.nintendo.com/api/HK/en/search/sales?count=5&offset=0",
          "https://ec.nintendo.com/api/HK/zh/search/new?count=5&offset=0",
          "https://ec.nintendo.com/api/JP/ja/search/sales?count=3&offset=0",
          "https://ec.nintendo.com/api/HK/zh/search/?q=mario&count=3",
          "https://www.dekudeals.com/games?country=hk&filter[store]=eshop",
          "https://psprices.com/region-th/collection/most-wanted-deals?platform=PS5"]:
    s, h = get(u)
    print("==", u, s, len(h), h[:700].replace("\n", " "))
ids = "70010000050752,70010000096809,70010000060917"
s, h = get("https://api.ec.nintendo.com/v1/price?country=HK&lang=en&ids=" + ids)
print("HK price", s, h[:800])
