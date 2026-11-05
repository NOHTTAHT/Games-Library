# Small Supabase REST helper for the daily update (uses the secret key, so it bypasses the database rules).
# Env: SUPABASE_URL, SUPABASE_SECRET_KEY
import json, os, time, urllib.request, urllib.parse

URL = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/docs"
KEY = os.environ["SUPABASE_SECRET_KEY"]

def _req(method, url, body=None, headers=None):
    h = {"apikey": KEY, "Content-Type": "application/json"}
    if KEY.startswith("eyJ"):  # legacy service_role JWT
        h["Authorization"] = "Bearer " + KEY
    h.update(headers or {})
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    for t in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=120) as r:
                txt = r.read().decode()
                return json.loads(txt) if txt else None
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise SystemExit(f"SUPABASE_ERROR {e.code} {e.read().decode()[:300]}")
            time.sleep(3 * (t + 1))
        except Exception:
            time.sleep(3 * (t + 1))
    raise SystemExit("SUPABASE_UNREACHABLE")

def list_docs(coll):
    out = {}
    off = 0
    while True:
        q = urllib.parse.urlencode({"coll": "eq." + coll, "select": "id,data", "order": "id"})
        rows = _req("GET", f"{URL}?{q}", headers={"Range": f"{off}-{off + 199}", "Range-Unit": "items"})
        for r in rows:
            out[r["id"]] = r["data"]
        if len(rows) < 200:
            return out
        off += 200

def get_doc(coll, id):
    q = urllib.parse.urlencode({"coll": "eq." + coll, "id": "eq." + id, "select": "data"})
    rows = _req("GET", f"{URL}?{q}")
    return rows[0]["data"] if rows else None

def set_docs(coll, docs):
    """docs: {id: data}. Upserts in small batches."""
    items = [{"coll": coll, "id": k, "data": v, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} for k, v in docs.items()]
    chunk, size = [], 0
    for it in items + [None]:
        n = len(json.dumps(it, ensure_ascii=False)) if it else 0
        if chunk and (it is None or size + n > 800000 or len(chunk) >= 50):
            _req("POST", URL + "?on_conflict=coll,id", chunk, {"Prefer": "resolution=merge-duplicates,return=minimal"})
            chunk, size = [], 0
        if it: chunk.append(it); size += n

def delete_doc(coll, id):
    q = urllib.parse.urlencode({"coll": "eq." + coll, "id": "eq." + id})
    _req("DELETE", f"{URL}?{q}", headers={"Prefer": "return=minimal"})
