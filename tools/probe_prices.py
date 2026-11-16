# Temporary probe round 2
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
def nd(h):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    return json.loads(m.group(1)) if m else None
# 1) concept page: what price/offer fields exist
s, h = get("https://store.playstation.com/en-th/concept/10002456")
d = nd(h); st = (d or {}).get("props", {}).get("apolloState", {})
print("== concept apollo types", sorted({v.get("__typename") for v in st.values() if isinstance(v, dict)}))
for k, v in list(st.items()):
    if isinstance(v, dict) and v.get("__typename") in ("Product", "Concept"):
        print(k, json.dumps(v)[:1500]); 
for m in set(re.findall(r'"(endTime|startTime|endDate|offerEndTime|discountText|campaignId)":"?([^",}]*)', h)):
    print(" field", m)
# 2) deals page -> category links
s, h = get("https://store.playstation.com/en-th/pages/deals")
print("== deals", s, len(h))
cats = sorted(set(re.findall(r'/en-th/category/([0-9a-f-]{36})', h)))
print("categories", cats[:30])
for m in re.findall(r'"name":"([^"]{3,60})"[^{}]{0,200}?"categoryId":"([0-9a-f-]{36})"', h)[:30]:
    print(" ", m)
# 3) a category page SSR?
for c in cats[:3]:
    s, h = get(f"https://store.playstation.com/en-th/category/{c}/1")
    d = nd(h); st = (d or {}).get("props", {}).get("apolloState", {})
    prods = [v for v in st.values() if isinstance(v, dict) and v.get("__typename") == "Product"]
    print("== category", c, s, len(h), "products", len(prods))
    for v in prods[:3]: print("  ", json.dumps(v)[:700])
    grids = [ (k, {kk: vv for kk, vv in v.items() if kk not in ("products", "concepts")}) for k, v in st.items() if isinstance(v, dict) and v.get("__typename") == "CategoryGrid"]
    for g in grids[:2]: print("  grid", json.dumps(g)[:600])
    print("  title", re.findall(r"<title>(.*?)</title>", h)[:1])
# 4) GraphQL persisted queries (known hashes; may be stale)
G = "https://web.np.playstation.com/api/graphql/v1/op"
hd = {"x-psn-store-locale-override": "en-TH", "content-type": "application/json", "Origin": "https://store.playstation.com"}
tests = {
 "categoryGridRetrieve": ({"id": cats[0] if cats else "", "pageArgs": {"size": 5, "offset": 0}, "sortBy": None, "filterBy": [], "facetOptions": []}, "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"),
 "getSearchResults": ({"searchTerm": "elden ring", "pageOffset": 0, "pageSize": 5}, "a2fbc15433b37ca7bfcd7112f741735e13268f5e9ebd5ffce51b85acc126f41a"),
 "metGetPricingDataByConceptId": ({"conceptId": "10002456"}, "abcb311ea830e679fe2b697a27f755764535d825b24510ab1239a4ca3092bd09"),
}
for op, (var, hsh) in tests.items():
    u = G + "?" + urllib.parse.urlencode({"operationName": op, "variables": json.dumps(var), "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": hsh}})})
    s, h = get(u, hd)
    print("== gql", op, s, h[:900])
# 5) find hashes in JS bundles
s, h = get("https://store.playstation.com/en-th/search/elden%20ring")
srcs = re.findall(r'src="(/_next/static/[^"]+\.js)"', h) + re.findall(r'src="(https://[^"]+\.js)"', h)
print("== scripts", len(srcs))
found = set()
for src in srcs:
    u = src if src.startswith("http") else "https://store.playstation.com" + src
    s, js = get(u)
    for m in re.finditer(r'(getSearchResults|categoryGridRetrieve|searchFor\w*|metGetPricing\w*)[^;]{0,300}?([0-9a-f]{64})', js):
        found.add((m.group(1), m.group(2)))
    if "sha256Hash" in js: print("  sha in", u[-60:])
print(found)
# 6) Nintendo HK: list entries with sale + price API
s, h = get("https://www.nintendo.com.hk/data/json/switch_software.json")
lst = json.loads(h); print("== HK list", len(lst), "keys", list(lst[0]))
sale = [x for x in lst if x.get("sale_until")]
print("on sale entries", len(sale), [ (x["title"], x["sale_until"], x["thumb_img"]) for x in sale[:5]])
ids = [re.sub(r"\D", "", x["thumb_img"]) for x in (sale[:5] + lst[:5]) if re.match(r"7001\d+", x.get("thumb_img", ""))]
s, h = get("https://api.ec.nintendo.com/v1/price?country=HK&lang=en&ids=" + ",".join(ids))
print("HK price", s, h[:1500])
s, h = get("https://api.ec.nintendo.com/v1/price?country=TH&lang=en&ids=" + ",".join(ids))
print("TH price", s, h[:300])
