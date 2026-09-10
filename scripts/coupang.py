# -*- coding: utf-8 -*-
"""쿠팡파트너스 Open API 클라이언트 (HMAC CEA 서명)"""
import hmac, hashlib, os, json, ssl, urllib.request, urllib.parse
from datetime import datetime, timezone

DOMAIN = "https://api-gateway.coupang.com"
BASE   = "/v2/providers/affiliate_open_api/apis/openapi/v1"

def load_keys(path=None):
    # GitHub Actions 에서는 비밀값이 환경변수로 들어옵니다. 둘 다 있으면 그걸 씁니다.
    env = {k: os.environ[k] for k in ("COUPANG_ACCESS_KEY", "COUPANG_SECRET_KEY") if os.environ.get(k)}
    if len(env) == 2:
        return env
    path = path or os.path.expanduser("~/.hyetaekzone.env")
    keys = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    return keys

def _auth(method, path, query, access, secret):
    dt = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    msg = dt + method + path + query
    sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={access}, "
            f"signed-date={dt}, signature={sig}")

def call(method, path, query="", body=None, keys=None):
    keys = keys or load_keys()
    access = keys.get("COUPANG_ACCESS_KEY", "")
    secret = keys.get("COUPANG_SECRET_KEY", "")
    if not access or not secret:
        raise RuntimeError("쿠팡 키가 비어 있습니다 (~/.hyetaekzone.env)")

    url = DOMAIN + path + (("?" + query) if query else "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth(method, path, query, access, secret))
    req.add_header("Content-Type", "application/json;charset=UTF-8")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:    return e.code, json.loads(raw)
        except Exception: return e.code, {"raw": raw[:600]}

def goldbox(limit=20, sub_id=None):
    q = urllib.parse.urlencode({k: v for k, v in
        {"limit": limit, "subId": sub_id}.items() if v is not None})
    return call("GET", f"{BASE}/products/goldbox", q)

def best_category(category_id, limit=20, sub_id=None):
    q = urllib.parse.urlencode({k: v for k, v in
        {"limit": limit, "subId": sub_id}.items() if v is not None})
    return call("GET", f"{BASE}/products/bestcategories/{category_id}", q)

def search(keyword, limit=10, sub_id=None):
    q = urllib.parse.urlencode({k: v for k, v in
        {"keyword": keyword, "limit": limit, "subId": sub_id}.items() if v is not None})
    return call("GET", f"{BASE}/products/search", q)

def deeplink(urls, sub_id=None):
    """쿠팡 주소를 제휴 링크로 바꾼다. data: [{originalUrl, shortenUrl, landingUrl}]"""
    body = {"coupangUrls": list(urls)}
    if sub_id:
        body["subId"] = sub_id
    return call("POST", f"{BASE}/deeplink", "", body)
