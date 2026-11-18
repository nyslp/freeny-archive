"""Check every page in dist/: one <h1>, title/description present and sane, JSON-LD parses,
canonical set, and every internal link, image and stylesheet resolves to a file."""
import json, os, re, sys, collections
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
BASE = json.load(open(os.path.join(ROOT, "site.config.json")))["site_url"].rstrip("/")

class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.h1 = 0; s.refs = []; s.ld = []; s.inld = False; s.meta = {}; s.title = ""; s.intitle = False; s.canon = None
    def handle_starttag(s, t, a):
        a = dict(a)
        if t == "h1": s.h1 += 1
        if t == "title": s.intitle = True
        if t in ("a", "link") and a.get("href"): s.refs.append(a["href"])
        if t in ("img", "script") and a.get("src"): s.refs.append(a["src"])
        if t == "link" and a.get("rel") == "canonical": s.canon = a["href"]
        if t == "meta" and (a.get("name") or a.get("property")): s.meta[a.get("name") or a.get("property")] = a.get("content")
        if t == "script" and a.get("type") == "application/ld+json": s.inld = True; s.ld.append("")
    def handle_endtag(s, t):
        if t == "script": s.inld = False
        if t == "title": s.intitle = False
    def handle_data(s, d):
        if s.inld: s.ld[-1] += d
        if s.intitle: s.title += d

def target(href):
    u = urlparse(href)
    if u.scheme in ("http", "https") and not href.startswith(BASE): return None
    if u.scheme in ("mailto", "tel") or href.startswith("#"): return None
    path = unquote(urlparse(href.replace(BASE, "")).path)
    if path.endswith("/"): path += "index.html"
    return os.path.join(DIST, path.lstrip("/"))

errs, warns, pages = [], collections.Counter(), 0
titles = collections.Counter()
for r, _, fs in os.walk(DIST):
    for f in fs:
        if not f.endswith(".html"): continue
        pages += 1
        p = os.path.join(r, f); rel = os.path.relpath(p, DIST)
        x = P(); x.feed(open(p).read())
        if x.h1 != 1: errs.append(f"{rel}: {x.h1} <h1>")
        if not x.canon: errs.append(f"{rel}: no canonical")
        d = x.meta.get("description") or ""
        if not (50 <= len(d) <= 170): warns["description length outside 50-170"] += 1
        if len(x.title) > 75: warns["title over 75 chars"] += 1
        titles[x.title] += 1
        for blob in x.ld:
            try: json.loads(blob)
            except Exception as ex: errs.append(f"{rel}: bad JSON-LD {ex}")
        for h in x.refs:
            t = target(h)
            if t and not os.path.exists(t) and "/search/?" not in h and "fonts.g" not in h:
                errs.append(f"{rel}: broken link {h}")
dupe = [t for t, n in titles.items() if n > 1]
print(f"{pages} pages checked")
print("errors:", len(errs)); [print("  ", e) for e in errs[:25]]
print("warnings:", dict(warns)); print("duplicate titles:", dupe[:10])
sys.exit(1 if errs else 0)
