# Temporary probe: can a GitHub runner read Thai store prices?
import json, re, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-TH,en;q=0.9"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, repr(e)
for q in ["elden ring", "astro bot", "ghost of yotei", "stellar blade"]:
    s, h = get("https://store.playstation.com/en-th/search/" + urllib.parse.quote(q))
    print("== PS search", q, s, len(h))
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        print(h[:800]); continue
    d = json.loads(m.group(1))
    st = d.get("props", {}).get("apolloState") or {}
    print("apollo keys", len(st), list(st)[:8])
    n = 0
    for k, v in st.items():
        if isinstance(v, dict) and v.get("price") and v.get("name"):
            print(" ", k, "|", v.get("name"), "|", v.get("platforms"), "|", v.get("storeDisplayClassification"), "|", json.dumps(v.get("price"))[:300])
            n += 1
            if n > 6: break
    if n == 0:
        print(json.dumps(d)[:3000])
s, h = get("https://store.playstation.com/en-th/concept/10002456")
print("== PS concept", s, len(h))
for m in re.finditer(r'"(basePrice|discountedPrice|discountText)":"([^"]*)"', h):
    print(" ", m.group(1), m.group(2))
for c in ["TH", "HK", "SG"]:
    s, h = get(f"https://api.ec.nintendo.com/v1/price?country={c}&lang=en&ids=70010000063714,70010000063715")
    print("== Nintendo price", c, s, h[:400])
s, h = get("https://www.nintendo.com.hk/data/json/switch_software.json")
print("== Nintendo HK list", s, len(h), h[:600])
