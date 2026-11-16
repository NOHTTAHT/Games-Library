# Temporary probe round 4
import json, re, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
def get(u, h=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={**UA, **(h or {})}), timeout=60) as r:
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
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in ("mobilectas", "param", "__typename", "media")}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
for c in ["3f772501-f6f8-49b7-abac-874a88ca4897"]:
    s, h = gql("categoryGridRetrieve", {"id": c, "pageArgs": {"size": 200, "offset": 0}, "sortBy": None, "filterBy": [], "facetOptions": []}, CG)
    g = json.loads(h)["data"]["categoryGridRetrieve"]
    print("== cat", c, json.dumps(strip({k: v for k, v in g.items() if k not in ("products", "concepts")}))[:600])
    ps = g.get("products") or []
    print("  keys:", sorted(ps[0].keys()), json.dumps(ps[0].get("concept")))
    disc = [p for p in ps if (p.get("price") or {}).get("discountText")]
    print("  discounted in first 200:", len(disc))
    for p in disc[:3]: print("   ", p["name"], p.get("platforms"), json.dumps(p.get("price")))
s, h = gql("metGetPricingDataByConceptId", {"conceptId": "10002456"}, "abcb311ea830e679fe2b697a27f755764535d825b24510ab1239a4ca3092bd09")
t = json.dumps(strip(json.loads(h)))
for m in re.finditer(r"endTime|basePrice|discountText", t): print("   pricing ctx:", t[max(0,m.start()-300):m.start()+200])
for op, hsh in [("productRetrieveForCtasWithPrice", "8532da7eda369efdad054ca8f885394a2d0c22d03c5259a422ae2bb3b98c5c99"),
                ("productRetrieveForUpsellWithCtas", "fb0bfa0af4d8dc42b28fa5c077ed715543e7fb8a3deff8117a50b99864d246f1")]:
    s, h = gql(op, {"productId": "EP3969-PPSA11386_00-007FIRSTLIGHT000"}, hsh)
    print("==", op, s, json.dumps(strip(json.loads(h)))[:1500] if s == 200 else h[:300])
s, h = get("https://store.playstation.com/en-th/product/EP3969-PPSA11386_00-007FIRSTLIGHT000")
print("== product page", s, len(h), re.findall(r'"(endTime|startTime)":"?([^",}]*)', h)[:10])
s, h = get("https://www.nintendo.com.hk/data/json/switch_software.json")
lst = json.loads(h)
nsu = [x for x in lst if re.match(r"7001\d{10}", x.get("thumb_img", ""))]
print("== HK list", len(lst), "with nsuid", len(nsu), "platforms", sorted({x.get('platform') for x in lst}))
print(" sample", [(x["title"], x["thumb_img"], x.get("price"), x.get("link")) for x in lst[:6]])
ids = [x["thumb_img"][:14] for x in nsu[:50]]
s, h = get("https://api.ec.nintendo.com/v1/price?country=HK&lang=en&ids=" + ",".join(ids))
pr = json.loads(h)["prices"]
print(" HK prices", sum(1 for p in pr if p.get("sales_status") == "onsale"), "onsale of", len(pr), "discounted:", [p for p in pr if p.get("discount_price")][:2])
for u in ["https://open.er-api.com/v6/latest/HKD", "https://api.frankfurter.app/latest?from=HKD&to=THB",
          "https://www.nintendo.com/hk/", "https://store.nintendo.com.hk/", "https://www.nintendo.com.hk/software/switch/index.html"]:
    s, h = get(u); print("==", u, s, h[:300].replace("\n", " "))
