"""Stage 4: render site/data.json into a static, crawlable website in dist/.

Every article, issue, topic, county and author gets its own HTML page with full
metadata (canonical URL, Open Graph, JSON-LD), plus sitemap.xml, robots.txt,
feed.xml, llms.txt, llms-full.txt and a Markdown copy of every article for AI tools.
"""
import calendar, html, json, os, re, shutil
from datetime import date, datetime, timezone
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "site.config.json")))
BASE = CFG["site_url"].rstrip("/")
DIST = os.path.join(ROOT, "dist")
D = json.load(open(os.path.join(ROOT, "site/data.json")))
OLDER = os.path.join(os.path.dirname(ROOT), "FreeNY-pdfs.md")

ISS = {i["key"]: i for i in D["issues"]}
FEED_KINDS = {"article", "updates", "other"}
KIND_LABEL = {"article": "Article", "updates": "LPNY Updates", "county-news": "County Affiliate News",
              "directory": "Directory", "ad": "Notice", "other": "Statement"}
BOROUGH = {"Kings": "Kings County (Brooklyn)", "New York": "New York County (Manhattan)",
           "Queens": "Queens County", "Richmond": "Richmond County (Staten Island)", "Bronx": "Bronx County"}
ORG_WORDS = ("Party", "Campaign", "Committee")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def slug(s):
    s = re.sub(r"[‐-―/]", " ", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s.encode("ascii", "ignore").decode())
    return s.strip("-")


def county_name(c):
    return BOROUGH.get(c, f"{c} County")


def is_org(name):
    return any(w in name for w in ORG_WORDS)


# ---------------------------------------------------------------- URLs
def art_url(a):
    y, m = a["issue"].split("-")
    return f"/{y}/{m}/{a['slug'][8:]}/"


def issue_url(k): return f"/issues/{k}/"
def tag_url(t): return f"/topics/{slug(t)}/"
def county_url(c): return f"/counties/{slug(c)}/"
def author_url(n): return f"/authors/{slug(n)}/"
def abs_(u): return BASE + u


ARTS = D["articles"]
pos = {s: (i["key"], k) for i in D["issues"] for k, s in enumerate(i["articles"])}
ORDER = sorted(ARTS, key=lambda a: (pos[a["slug"]][0], -pos[a["slug"]][1]), reverse=True)
BY_SLUG = {a["slug"]: a for a in ARTS}
TITLE_COUNT = {}
for a in ARTS:
    TITLE_COUNT[a["title"].lower()] = TITLE_COUNT.get(a["title"].lower(), 0) + 1
for a in ARTS:
    a["url"] = art_url(a)
    a["date"] = a["issue"] + "-01"
    a["indexable"] = a["kind"] != "ad"


def counts(key, pool=None):
    m = {}
    for a in pool or ORDER:
        vals = a[key] if isinstance(a[key], list) else ([a[key]] if a[key] else [])
        for v in vals:
            m[v] = m.get(v, 0) + 1
    return sorted(m.items(), key=lambda x: (-x[1], x[0]))


AUTHORS = [(n, c) for n, c in counts("author") if not is_org(n) and " and " not in n]


# ---------------------------------------------------------------- text helpers
def linkify(t):
    t = e(t)
    t = re.sub(r"\b(https?://[^\s<]+[^\s<.,;:)])", r'<a href="\1" rel="noopener">\1</a>', t)
    t = re.sub(r"(^|[\s(])(www\.[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<]*[^\s<.,;:)])?)", r'\1<a href="https://\2" rel="noopener">\2</a>', t, flags=re.I)
    return t


def clip(s, n=158):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def plain_body(a):
    out = []
    for b in a["body"]:
        if b["t"] in ("p", "quote", "h"):
            out.append(b["text"])
        elif b["t"] == "list":
            out.append(" ".join(b["lines"]))
    return " ".join(out)


def describe(a):
    d = clip(a.get("summary") or plain_body(a))
    if len(d) < 80:
        d = clip(f"{d} From {CFG['periodical']}, the Libertarian Party of New York newsletter, {ISS[a['issue']]['label']}.".strip())
    return d


def seo_title(a):
    """Recurring titles (County Affiliate News, LPNY Directory, repeated ads) get the issue month."""
    t = a["title"]
    return f"{t}, {ISS[a['issue']]['label']}" if TITLE_COUNT.get(t.lower(), 0) > 1 else t


# ---------------------------------------------------------------- images
def thumb(src, w=360):
    """Write a small JPEG for lists and return its URL."""
    if not src:
        return None
    rel = src.replace(".jpg", f"-w{w}.jpg")
    out = os.path.join(DIST, rel)
    if not os.path.exists(out):
        im = Image.open(os.path.join(ROOT, "site", src)).convert("RGB")
        im.thumbnail((w, w * 2))
        im.save(out, "JPEG", quality=78, optimize=True, progressive=True)
    return "/" + rel


def img_size(src):
    with Image.open(os.path.join(ROOT, "site", src)) as im:
        return im.size


def make_og_default():
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (43, 43, 44))
    d = ImageDraw.Draw(im)
    sup = "/System/Library/Fonts/Supplemental/"
    try:
        hand = ImageFont.truetype(sup + "Bradley Hand Bold.ttf", 132)
        sans = ImageFont.truetype(sup + "Arial Bold.ttf", 34)
    except OSError:
        hand = sans = ImageFont.load_default()
    d.rectangle([0, 0, W, 18], fill=(227, 192, 0))
    d.text((80, 170), "Free New York", font=hand, fill=(255, 255, 255))
    d.text((84, 360), "THE NEWSLETTER OF THE LIBERTARIAN PARTY OF NEW YORK", font=sans, fill=(227, 192, 0))
    d.text((84, 412), f"Archive · {len(D['issues'])} issues · 2023–{D['issues'][0]['year']}", font=sans, fill=(220, 220, 214))
    im.save(os.path.join(DIST, "og-default.png"), optimize=True)
    return "/og-default.png"


# ---------------------------------------------------------------- page shell
CSS_SRC = open(os.path.join(ROOT, "site/index.html")).read()
CSS = CSS_SRC[CSS_SRC.index("<style>") + 7: CSS_SRC.index("</style>")]
CSS += """
.crumbs { font: 600 12.5px/1.4 var(--display); color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.crumbs a { text-decoration: none; } .crumbs a:hover { color: var(--ink); text-decoration: underline; }
.crumbs span[aria-hidden] { opacity: 0.6; }
.prose.page h2 { margin-top: 1.4em; }
.prose table { border-collapse: collapse; width: 100%; font: 500 14.5px/1.4 var(--display); }
.prose td, .prose th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--rule); vertical-align: top; }
.tablewrap { overflow-x: auto; }
.pager { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; }
.pager a { font: 800 14px var(--display); letter-spacing: 0.06em; text-transform: uppercase; text-decoration: none; border: 2px solid var(--ink); padding: 10px 16px; }
.pager a:hover { background: var(--ink); color: var(--bg); }
.search input { -webkit-appearance: none; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.item img { aspect-ratio: auto; }
"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=Caveat:wght@700'
         '&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">')
NAV = [("/", "Latest", "home"), ("/issues/", "All issues", "issues"), ("/county-affiliates/", "County affiliates", "county"),
       ("/updates/", "LPNY updates", "updates"), ("/topics/", "Topics", "topics"), ("/about/", "About", "about")]


def rail():
    by = {}
    for i in D["issues"]:
        by.setdefault(i["year"], {})[i["month"]] = i
    years = "".join(
        f'<div class="year"><b>{y}</b><div class="months">' + "".join(
            f'<a href="{issue_url(by[y][k + 1]["key"])}" title="{e(by[y][k + 1]["label"])}">{m}</a>' if (k + 1) in by[y]
            else f'<span aria-hidden="true">{m}</span>' for k, m in enumerate(MONTHS)) + "</div></div>"
        for y in sorted(by, reverse=True))
    tags = "".join(f'<a class="chip" href="{tag_url(t)}">{e(t)}<small>{n}</small></a>' for t, n in counts("tags")[:15])
    cs = "".join(f'<a class="chip" href="{county_url(c)}">{e(c)}<small>{n}</small></a>' for c, n in counts("counties")[:12])
    return (f'<section><h2 class="label">Issues</h2><div class="years">{years}</div></section>'
            f'<section><h2 class="label">Topics</h2><div class="chips">{tags}</div></section>'
            f'<section><h2 class="label">Counties</h2><div class="chips">{cs}</div></section>'
            f'<section class="about"><h2 class="label">About</h2><p><i>Free New York</i> is the monthly newsletter of the Libertarian Party of New York, '
            f'published under several names since 1972.</p><p><a href="/about/">About this archive</a></p></section>')


RAIL = None


def page(path, title, desc, body, *, nav="", ld=None, og_image=None, og_type="website", noindex=False,
         alt_md=None, extra_head="", full_title=None, scripts=""):
    global RAIL
    if RAIL is None:
        RAIL = rail()
    url = abs_(path)
    t = full_title or (f"{title} | {CFG['site_name']}" if title else CFG["site_name"])
    if len(t) > 70 and title and not full_title:
        t = f"{title} | Free New York" if len(title) <= 55 else title
    robots = "noindex, follow" if (noindex or not CFG["indexable"]) else "index, follow, max-image-preview:large, max-snippet:-1"
    img = abs_(og_image or OG_DEFAULT)
    head = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{e(t)}</title>", f'<meta name="description" content="{e(desc)}">',
        f'<link rel="canonical" href="{url}">', f'<meta name="robots" content="{robots}">',
        f'<meta property="og:site_name" content="{e(CFG["site_name"])}">', f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{e(title or CFG["site_name"])}">', f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{url}">', f'<meta property="og:image" content="{img}">', '<meta property="og:locale" content="en_US">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<link rel="alternate" type="application/atom+xml" title="{e(CFG["site_name"])}" href="{BASE}/feed.xml">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">', '<meta name="theme-color" content="#2b2b2c">',
    ]
    if alt_md:
        head.append(f'<link rel="alternate" type="text/markdown" href="{alt_md}">')
    head += [FONTS, '<link rel="stylesheet" href="/assets/site.css">', extra_head]
    for block in (ld or []):
        head.append('<script type="application/ld+json">' + json.dumps(block, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    navh = "".join(f'<a href="{u}"{" aria-current=\"page\"" if k == nav else ""}>{l}</a>' for u, l, k in NAV)
    doc = "".join(head) + "</head><body>" + f"""
<a class="sr" href="#main">Skip to content</a>
<header class="mast"><div class="wrap">
  <a class="brand" href="/"><span class="name">Free New York</span><span class="sub">Newsletter of the Libertarian Party of New York · Archive</span></a>
  <form class="search" role="search" action="/search/" method="get"><label class="sr" for="q">Search the archive</label>
    <input id="q" name="q" type="search" placeholder="Search every article" autocomplete="off"></form>
</div></header>
<nav class="bar" aria-label="Sections"><div class="wrap">{navh}</div></nav>
<main id="main"><div class="wrap"><div>{body}</div><aside aria-label="Browse the archive">{RAIL}</aside></div></main>
<footer><div class="wrap">Text and photos come from the PDF issues of <i>Free New York</i> published by the {e(CFG["publisher"])}
and archived on <a href="https://lpedia.org">LPedia</a>. Each article links to its original PDF page; the PDF is the record of what was printed.
· <a href="/about/">About</a> · <a href="/feed.xml">Feed</a> · <a href="/llms.txt">llms.txt</a></div></footer>
{scripts}</body></html>"""
    out = os.path.join(DIST, path.lstrip("/"), "index.html") if path.endswith("/") else os.path.join(DIST, path.lstrip("/"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(doc)
    if not noindex and CFG["indexable"]:
        SITEMAP.append((url, LASTMOD.get(path)))


SITEMAP, LASTMOD = [], {}


def crumbs(items):
    """items: [(label, url_or_None)]"""
    parts = []
    for k, (l, u) in enumerate(items):
        if k:
            parts.append('<span aria-hidden="true">›</span>')
        parts.append(f'<a href="{u}">{e(l)}</a>' if u else f"<span>{e(l)}</span>")
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": k + 1, "name": l, **({"item": abs_(u)} if u else {})} for k, (l, u) in enumerate(items)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb">{"".join(parts)}</nav>', ld


# ---------------------------------------------------------------- shared schema
PUBLISHER = {"@type": "Organization", "@id": CFG["publisher_url"] + "#org", "name": CFG["publisher"], "url": CFG["publisher_url"]}
PERIODICAL = {"@type": "Periodical", "@id": BASE + "/#periodical", "name": CFG["periodical"], "publisher": PUBLISHER,
              "url": BASE + "/", "inLanguage": "en", "startDate": "1972"}


def issue_ld(i):
    return {"@type": "PublicationIssue", "@id": abs_(issue_url(i["key"])) + "#issue", "name": f'{CFG["periodical"]}, {i["label"]}',
            "issueNumber": str(i["number"]) if i.get("number") else None, "datePublished": i["key"] + "-01",
            "url": abs_(issue_url(i["key"])), "isPartOf": {"@type": "PublicationVolume", "volumeNumber": str(i["volume"]), "isPartOf": PERIODICAL}
            if i.get("volume") else PERIODICAL, "encoding": {"@type": "MediaObject", "encodingFormat": "application/pdf", "contentUrl": i["pdf"]}}


def author_ld(a):
    if not a.get("author"):
        return PUBLISHER
    if is_org(a["author"]):
        return {"@type": "Organization", "name": a["author"]}
    p = {"@type": "Person", "name": a["author"]}
    if a["author"] in dict(AUTHORS):
        p["url"] = abs_(author_url(a["author"]))
    if a.get("role"):
        p["jobTitle"] = a["role"]
    return p


# ---------------------------------------------------------------- list item
def item(a, show_issue=True):
    i = ISS[a["issue"]]
    bits = [f'<a href="{issue_url(i["key"])}">{e(i["label"])}</a>'] if show_issue else []
    if a["kind"] != "article":
        bits.append(e(KIND_LABEL[a["kind"]]))
    elif a["tags"]:
        bits.append(f'<a href="{tag_url(a["tags"][0])}">{e(a["tags"][0])}</a>')
    by = ""
    if a.get("author"):
        name = f'<a href="{author_url(a["author"])}">{e(a["author"])}</a>' if a["author"] in dict(AUTHORS) else e(a["author"])
        by = f'<div class="by">By {name}{", " + e(a["role"]) if a.get("role") else ""}</div>'
    th = thumb(a["lead"]) if a["lead"] else None
    img = f'<a href="{a["url"]}" tabindex="-1" aria-hidden="true"><img src="{th}" alt="" loading="lazy" width="132" height="100"></a>' if th else ""
    return (f'<article class="item{"" if th else " noimg"}"><div><div class="kicker">{" · ".join(bits)}</div>'
            f'<h3><a href="{a["url"]}">{e(a["title"])}</a></h3><p>{e(a.get("summary") or describe(a))}</p>{by}</div>{img}</article>')


def listing(path, title, intro, arts, *, label=None, nav="", crumb=None, extra="", ld_extra=None, desc=None, show_issue=True):
    cr, crld = crumbs(crumb or [("Home", "/"), (title, None)])
    head = (f'{cr}<div class="pagehead">{f"<span class=label>{e(label)}</span>" if label else ""}<h1>{e(title)}</h1>'
            f'{f"<p>{intro}</p>" if intro else ""}{extra}</div>')
    body = head + (f'<div class="feed">{"".join(item(a, show_issue) for a in arts)}</div>' if arts else '<p class="empty">Nothing here yet.</p>')
    coll = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": abs_(path), "isPartOf": {"@id": BASE + "/#website"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(arts), "itemListElement": [
                {"@type": "ListItem", "position": k + 1, "url": abs_(a["url"]), "name": a["title"]} for k, a in enumerate(arts[:100])]}}
    if ld_extra:
        coll.update(ld_extra)
    page(path, title, desc or clip(re.sub("<[^>]+>", "", intro or "") or f"{title} in the {CFG['site_name']}."), body, nav=nav, ld=[coll, crld])


# ---------------------------------------------------------------- article page
LBL = re.compile(r"^(NEXT MEETINGS?|MONTHLY SOCIAL|CONTACTS?|LEARN MORE|MEETINGS?|EVENTS?|SOCIAL)\s*:?\s*")


def county_line(l):
    m = LBL.match(l)
    if m:
        rest = l[m.end():]
        return f'<li class="lbl">{e(m.group(1).lower())}</li>' + (f"<li>{linkify(rest)}</li>" if rest else "")
    return f"<li>{linkify(l)}</li>"


def render_body(a):
    out = []
    if a["kind"] == "county-news":
        cells, cur, pre = [], None, []
        for b in a["body"]:
            if b["t"] == "h":
                cur = {"h": b["text"], "parts": []}
                cells.append(cur)
                continue
            if b["t"] == "list":
                h = f'<ul class="lines">{"".join(county_line(l) for l in b["lines"])}</ul>'
            elif b["t"] == "img":
                h = f'<figure><img src="/{b["src"]}" alt="" loading="lazy" width="{b["w"]}" height="{b["h"]}"></figure>'
            else:
                h = f"<p>{linkify(b['text'])}</p>"
            (cur["parts"] if cur else pre).append(h)
        return "".join(pre) + '<div class="cgrid">' + "".join(
            f'<section class="cell"><h2><span>{e(c["h"])}</span></h2>{"".join(c["parts"])}</section>' for c in cells) + "</div>"
    county = a["kind"] == "directory"
    for n, b in enumerate(a["body"]):
        t = b["t"]
        if t == "p":
            out.append(f"<p>{linkify(b['text'])}</p>")
        elif t == "h":
            out.append(f'<h2><span>{e(b["text"])}</span></h2>' if county else f"<h2>{e(b['text'])}</h2>")
        elif t == "quote":
            out.append(f"<blockquote><p>{linkify(b['text'])}</p></blockquote>")
        elif t == "list":
            out.append(f'<ul class="lines">{"".join(f"<li>{linkify(l)}</li>" for l in b["lines"])}</ul>')
        elif t == "img":
            alt = b.get("cap") or f"Photo from {a['title']}"
            lazy = "" if n < 2 else ' loading="lazy"'
            out.append(f'<figure><img src="/{b["src"]}" alt="{e(alt)}" width="{b["w"]}" height="{b["h"]}"{lazy}>'
                       + (f"<figcaption>{e(b['cap'])}</figcaption>" if b.get("cap") else "") + "</figure>")
    return "".join(out)


def article_md(a):
    i = ISS[a["issue"]]
    lines = [f"# {a['title']}", ""]
    if a.get("subtitle"):
        lines += [f"*{a['subtitle']}*", ""]
    meta = [f"- Published in: {CFG['periodical']}, {i['label']}" + (f" (Vol. {i['volume']}, No. {i['number']})" if i.get("volume") else ""),
            f"- Publisher: {CFG['publisher']}"]
    if a.get("author"):
        meta.append(f"- Author: {a['author']}" + (f", {a['role']}" if a.get("role") else ""))
    meta += [f"- Web page: {abs_(a['url'])}", f"- Original PDF: {i['pdf']}#page={a['pages'][0] if a['pages'] else 1}"]
    if a["tags"]:
        meta.append(f"- Topics: {', '.join(a['tags'])}")
    if a["counties"]:
        meta.append(f"- Counties: {', '.join(county_name(c) for c in a['counties'])}")
    lines += meta + [""]
    if a.get("summary"):
        lines += [f"> {a['summary']}", ""]
    for b in a["body"]:
        if b["t"] == "p":
            lines += [b["text"], ""]
        elif b["t"] == "h":
            lines += [f"## {b['text']}", ""]
        elif b["t"] == "quote":
            lines += [f"> {b['text']}", ""]
        elif b["t"] == "list":
            lines += [f"- {l}" for l in b["lines"]] + [""]
        elif b["t"] == "img":
            lines += [f"![{b.get('cap') or 'Photo'}]({BASE}/{b['src']})", ""]
    return "\n".join(lines).rstrip() + "\n"


def render_article(a):
    i = ISS[a["issue"]]
    sib = [BY_SLUG[s] for s in i["articles"]]
    k = sib.index(a)
    prev, nxt = (sib[k - 1] if k else None), (sib[k + 1] if k + 1 < len(sib) else None)
    pg = a["pages"][0] if a["pages"] else 1
    pages_txt = f"pages {a['pages'][0]}–{a['pages'][-1]}" if len(a["pages"]) > 1 else f"page {pg}"
    tl = a["tags"][0] if a["tags"] else None
    cr_items = [("Home", "/"), (i["label"], issue_url(i["key"])), (a["title"], None)]
    cr, crld = crumbs(cr_items)
    kick = [f'<a href="{issue_url(i["key"])}"><time datetime="{a["date"]}">{e(i["label"])}</time></a>']
    kick.append(e(KIND_LABEL[a["kind"]]) if a["kind"] != "article" else (f'<a href="{tag_url(tl)}">{e(tl)}</a>' if tl else ""))
    by = ""
    if a.get("author"):
        name = f'<a href="{author_url(a["author"])}" rel="author">{e(a["author"])}</a>' if a["author"] in dict(AUTHORS) else e(a["author"])
        role = f" <span>· {e(a['role'])}</span>" if a.get("role") else ""
        by = f'<div class="byline">By {name}{role}</div>'
    chips = "".join([f'<a class="chip" href="{tag_url(t)}">{e(t)}</a>' for t in a["tags"]] +
                    [f'<a class="chip" href="{county_url(c)}">{e(county_name(c))}</a>' for c in a["counties"]])
    md_url = a["url"] + "index.md"
    volno = f" (Vol. {i['volume']}, No. {i['number']})" if i.get("volume") else ""
    body = (f'{cr}<article class="story{" wide" if a["kind"] == "county-news" else ""}"><header><div class="kicker">{" · ".join(x for x in kick if x)}</div>'
            f'<h1>{e(a["title"])}</h1>' + (f'<p class="dek">{e(a["subtitle"])}</p>' if a.get("subtitle") else "") + by + "</header>"
            f'<div class="prose{" county" if a["kind"] in ("county-news", "directory") else ""}">'
            f'{render_body(a) or "<p class=empty>This item is a flyer or graphic. See the original PDF.</p>"}</div>'
            f'<div class="endnote"><div>From <a href="{issue_url(i["key"])}"><b>{e(CFG["periodical"])}, {e(i["label"])}</b></a>'
            f'{volno}, {pages_txt}. '
            f'<a href="{i["pdf"]}#page={pg}" rel="noopener">See it in the original PDF ↗</a> · <a href="{md_url}">Plain text (Markdown)</a></div>'
            + (f'<div class="chips">{chips}</div>' if chips else "") + "</div>"
            f'<nav class="pn" aria-label="More from this issue">'
            + (f'<a href="{prev["url"]}" rel="prev"><span>← Previous in this issue</span>{e(prev["title"])}</a>' if prev else "<span></span>")
            + (f'<a class="next" href="{nxt["url"]}" rel="next"><span>Next in this issue →</span>{e(nxt["title"])}</a>' if nxt else "<span></span>")
            + "</nav></article>")
    img = thumb(a["lead"], 1200) if a["lead"] else None
    typ = "NewsArticle" if a["kind"] in ("article", "updates", "other") else "Article"
    ld = {"@context": "https://schema.org", "@type": typ, "@id": abs_(a["url"]) + "#article", "headline": a["title"][:110],
          "name": a["title"], "description": describe(a), "datePublished": a["date"], "dateModified": a["date"], "inLanguage": "en",
          "url": abs_(a["url"]), "mainEntityOfPage": abs_(a["url"]), "author": author_ld(a), "publisher": PUBLISHER,
          "isPartOf": issue_ld(i), "isBasedOn": f"{i['pdf']}#page={pg}", "wordCount": a["words"],
          "articleSection": KIND_LABEL[a["kind"]], "isAccessibleForFree": True}
    if a.get("subtitle"):
        ld["alternativeHeadline"] = a["subtitle"]
    if a["tags"]:
        ld["keywords"] = ", ".join(a["tags"])
    if a["counties"]:
        ld["contentLocation"] = [{"@type": "AdministrativeArea", "name": f"{county_name(c)}, New York"} for c in a["counties"]]
    if img:
        ld["image"] = [abs_(img)]
    LASTMOD[a["url"]] = a["date"]
    page(a["url"], seo_title(a), describe(a), body, ld=[ld, crld], og_image=img, og_type="article", noindex=not a["indexable"],
         alt_md=md_url, extra_head=f'<meta property="article:published_time" content="{a["date"]}">'
         + (f'<meta property="article:author" content="{e(a["author"])}">' if a.get("author") else "")
         + "".join(f'<meta property="article:tag" content="{e(t)}">' for t in a["tags"]))
    open(os.path.join(DIST, a["url"].lstrip("/"), "index.md"), "w").write(article_md(a))


# ---------------------------------------------------------------- other pages
def render_home():
    feed = [a for a in ORDER if a["kind"] in FEED_KINDS]
    newest = feed[0]["issue"]
    lead = next((a for a in feed if a["lead"] and a["issue"] == newest), feed[0])
    rest = [a for a in feed if a is not lead][:30]
    li = thumb(lead["lead"], 900) if lead["lead"] else None
    body = (f'<h1 class="sr">{e(CFG["site_name"])}: articles from {e(CFG["periodical"])}, the newsletter of the {e(CFG["publisher"])}</h1>'
            f'<section class="lead-story{"" if li else " noimg"}">'
            + (f'<a href="{lead["url"]}" tabindex="-1" aria-hidden="true"><img src="{li}" alt=""></a>' if li else "")
            + f'<div><div class="kicker"><a href="{issue_url(lead["issue"])}">{e(ISS[lead["issue"]]["label"])}</a></div>'
            f'<h2><a href="{lead["url"]}">{e(lead["title"])}</a></h2><p>{e(lead.get("summary") or "")}</p></div></section>'
            f'<div class="feed">{"".join(item(a) for a in rest)}</div>'
            f'<div class="pager"><a href="/issues/">Browse all {len(D["issues"])} issues</a><a href="/topics/">Browse by topic</a></div>')
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "@id": BASE + "/#website", "name": CFG["site_name"], "url": BASE + "/",
               "description": CFG["description"], "inLanguage": "en", "publisher": PUBLISHER, "about": PERIODICAL,
               "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": BASE + "/search/?q={search_term_string}"},
                                   "query-input": "required name=search_term_string"}}
    LASTMOD["/"] = feed[0]["date"]
    page("/", None, CFG["description"], body, nav="home", ld=[site_ld, PUBLISHER | {"@context": "https://schema.org"}, PERIODICAL | {"@context": "https://schema.org"}],
         full_title=f"{CFG['site_name']}: the Libertarian Party of New York newsletter")


def render_issues():
    rows = []
    for i in D["issues"]:
        arts = [BY_SLUG[s] for s in i["articles"] if BY_SLUG[s]["kind"] != "ad"]
        th = thumb(i["cover"]) if i.get("cover") else None
        rows.append(f'<article class="item{"" if th else " noimg"}"><div><div class="kicker">Vol. {e(i.get("volume") or "–")}, No. {e(i.get("number") or "–")} · {i["pages"]} pages</div>'
                    f'<h3><a href="{issue_url(i["key"])}">{e(i["label"])}</a></h3><p>{" · ".join(e(a["title"]) for a in arts[:6])}</p></div>'
                    + (f'<a href="{issue_url(i["key"])}" tabindex="-1" aria-hidden="true"><img src="{th}" alt="" loading="lazy"></a>' if th else "") + "</article>")
    cr, crld = crumbs([("Home", "/"), ("All issues", None)])
    body = (f'{cr}<div class="pagehead"><h1>All issues</h1><p>{len(D["issues"])} monthly issues of <i>{e(CFG["periodical"])}</i>, newest first. '
            f'Older issues back to 1972 are listed on the <a href="/about/#older-issues">About page</a>.</p></div><div class="feed">{"".join(rows)}</div>')
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "All issues", "url": abs_("/issues/"),
          "hasPart": [{"@type": "PublicationIssue", "name": f'{CFG["periodical"]}, {i["label"]}', "url": abs_(issue_url(i["key"]))} for i in D["issues"]]}
    page("/issues/", "All issues", f"Every issue of {CFG['periodical']}, the Libertarian Party of New York newsletter, from {D['issues'][-1]['label']} to {D['issues'][0]['label']}.",
         body, nav="issues", ld=[ld, crld])
    for i in D["issues"]:
        arts = [BY_SLUG[s] for s in i["articles"]]
        LASTMOD[issue_url(i["key"])] = i["key"] + "-01"
        heads = [a["title"] for a in arts if a["kind"] in FEED_KINDS][:3]
        listing(issue_url(i["key"]), f"{CFG['periodical']}, {i['label']}",
                f"Vol. {e(i.get('volume') or '–')}, No. {e(i.get('number') or '–')} · {i['pages']} pages · {len(arts)} items",
                arts, label="Issue", crumb=[("Home", "/"), ("All issues", "/issues/"), (i["label"], None)], show_issue=False,
                extra=f'<a class="pdfbtn" href="{i["pdf"]}" rel="noopener">Open the original PDF ↗</a>',
                ld_extra={"about": issue_ld(i)},
                desc=clip(f"The {i['label']} issue of {CFG['periodical']}, the Libertarian Party of New York newsletter: " + "; ".join(heads) + "."))


def render_taxonomies():
    tg, ct = counts("tags"), counts("counties")
    cr, crld = crumbs([("Home", "/"), ("Topics", None)])
    body = (f'{cr}<div class="pagehead"><h1>Topics, counties and authors</h1><p>Every article is tagged with a few topics and the counties it covers.</p></div>'
            f'<div class="section-row"><h2 class="label">Topics</h2></div><div class="chips">' + "".join(f'<a class="chip" href="{tag_url(t)}">{e(t)}<small>{n}</small></a>' for t, n in tg) + "</div>"
            f'<div class="section-row"><h2 class="label">Counties</h2></div><div class="chips">' + "".join(f'<a class="chip" href="{county_url(c)}">{e(county_name(c))}<small>{n}</small></a>' for c, n in ct) + "</div>"
            f'<div class="section-row"><h2 class="label">Authors</h2></div><div class="chips">' + "".join(f'<a class="chip" href="{author_url(a)}">{e(a)}<small>{n}</small></a>' for a, n in AUTHORS) + "</div>")
    page("/topics/", "Topics", "Browse Free New York articles by topic, by New York county and by author.", body, nav="topics", ld=[crld])
    for t, _ in tg:
        arts = [a for a in ORDER if t in a["tags"] and a["kind"] != "ad"]
        listing(tag_url(t), f"Articles about {t}", f"Articles from {e(CFG['periodical'])} about {e(t)}.", arts,
                label="Topic", nav="topics", crumb=[("Home", "/"), ("Topics", "/topics/"), (t, None)],
                desc=clip(f"{len(arts)} articles about {t} from {CFG['periodical']}, the Libertarian Party of New York newsletter, including \u201c{arts[0]['title']}\u201d."))
    for c, _ in ct:
        listing(county_url(c), county_name(c), f"Libertarian Party news from {e(county_name(c))}, New York. Meeting times and contacts are on each issue's County Affiliate News page.",
                [a for a in ORDER if c in a["counties"]], label="County", nav="topics", crumb=[("Home", "/"), ("Topics", "/topics/"), (county_name(c), None)])
    for n, _ in AUTHORS:
        arts = [a for a in ORDER if a.get("author") == n]
        roles = sorted({a["role"] for a in arts if a.get("role")}, key=lambda r: -sum(1 for a in arts if a.get("role") == r))
        intro = f"{len(arts)} article{'s' if len(arts) != 1 else ''} in {e(CFG['periodical'])}." + (f" Bylines: {e('; '.join(roles[:4]))}." if roles else "")
        listing(author_url(n), n, intro, arts, label="Author",
                desc=clip(f"Articles by {n}" + (f", {roles[0]}," if roles else "") + f" in {CFG['periodical']}, the Libertarian Party of New York newsletter: {len(arts)} article{'s' if len(arts) != 1 else ''}, most recently \u201c{arts[0]['title']}\u201d."), nav="topics", crumb=[("Home", "/"), ("Topics", "/topics/"), (n, None)],
                ld_extra={"about": {"@type": "Person", "name": n, **({"jobTitle": roles[0]} if roles else {})}})


def render_about():
    older = ""
    if os.path.exists(OLDER):
        rows = [l for l in open(OLDER).read().splitlines() if l.startswith("| 19") or l.startswith("| 2")]
        trs = []
        for r in rows:
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) < 3 or cells[0][:4] >= "2023":
                continue
            m = re.search(r"\((https?://[^)]+)\)", cells[2])
            trs.append(f'<tr><td>{e(cells[0])}</td><td>{e(cells[1]) or "–"}</td><td><a href="{m.group(1)}" rel="noopener">PDF ↗</a></td></tr>' if m else "")
        older = (f'<h2 id="older-issues">Older issues, 1972–1993</h2><p>LPedia also holds {len(trs)} earlier issues as scanned PDFs. They are not '
                 f'yet transcribed here. The newsletter was called <i>Free Libertarian</i> (1972–80), <i>FLP Insider</i> (1982), <i>FLP News</i> (1983–85), '
                 f'<i>New York Libertarian Party News</i> (1985) and <i>Free New York</i> (from 1986).</p><div class="tablewrap"><table><thead><tr><th>Issue</th><th>Title</th><th>Scan</th></tr></thead><tbody>'
                 + "".join(trs) + "</tbody></table></div>")
    cr, crld = crumbs([("Home", "/"), ("About", None)])
    body = (f'{cr}<article class="story"><header><h1>About this archive</h1></header><div class="prose page">'
            f'<p><i>{e(CFG["periodical"])}</i> is the official monthly newsletter of the {e(CFG["publisher"])} (LPNY). This archive republishes every issue from '
            f'{e(D["issues"][-1]["label"])} to {e(D["issues"][0]["label"])} as searchable web pages: {sum(1 for a in ARTS if a["kind"] in FEED_KINDS)} articles and updates, '
            f'plus each issue\'s county affiliate listings and party directory.</p>'
            f'<h2>Where the text comes from</h2><p>The text and photos were extracted from the PDF issues archived on <a href="https://lpedia.org">LPedia</a>, '
            f'the Libertarian Party\'s history wiki. Each article was then split out and labeled with its author, topics and the counties it covers. '
            f'Every page links to the exact page of the original PDF, which remains the record of what was printed. Spelling and wording are kept as published.</p>'
            f'<h2>For researchers and AI tools</h2><p>Every article is also available as plain Markdown (add <code>index.md</code> to any article address). '
            f'<a href="/llms.txt">llms.txt</a> lists every article with a summary, <a href="/llms-full.txt">llms-full.txt</a> holds the full text of the whole archive, '
            f'and <a href="/feed.xml">feed.xml</a> is an Atom feed of the latest articles. Pages carry schema.org metadata describing each article, issue and author.</p>'
            f'<h2>The Libertarian Party of New York</h2><p>Visit <a href="{CFG["publisher_url"]}">{e(CFG["publisher_url"].split("//")[1])}</a> to join, donate or find a county affiliate.</p>'
            f'{older}</div></article>')
    page("/about/", "About this archive", f"How the {CFG['site_name']} was made, where its text comes from, and links to older issues back to 1972.",
         body, nav="about", ld=[{"@context": "https://schema.org", "@type": "AboutPage", "name": "About this archive", "url": abs_("/about/")}, crld])


def render_search():
    idx = [{"u": a["url"], "t": a["title"], "s": a.get("summary") or "", "i": ISS[a["issue"]]["label"], "k": a["kind"],
            "b": plain_body(a)} for a in ORDER if a["kind"] != "ad"]
    json.dump(idx, open(os.path.join(DIST, "search-index.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    cr, crld = crumbs([("Home", "/"), ("Search", None)])
    body = (f'{cr}<div class="pagehead"><h1 id="sh">Search the archive</h1><p id="sp">Type a name, place or topic in the search box.</p></div>'
            '<div class="feed" id="results"></div>')
    js = """<script>
(() => {
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const q = (new URLSearchParams(location.search).get("q") || "").trim();
  const box = document.getElementById("q"); if (box) box.value = q;
  if (!q) return;
  document.getElementById("sh").textContent = "Search: \\u201c" + q + "\\u201d";
  document.title = "Search: " + q + " | Free New York Archive";
  fetch("/search-index.json").then(r => r.json()).then(idx => {
    const terms = q.toLowerCase().split(/\\s+/).filter(Boolean);
    const hits = [];
    for (const a of idx) {
      const t = a.t.toLowerCase(), h = (a.t + " " + a.s + " " + a.b).toLowerCase();
      if (terms.every(x => h.includes(x))) hits.push([terms.reduce((n, x) => n + (t.includes(x) ? 5 : 0) + (a.s.toLowerCase().includes(x) ? 2 : 0), 0), a]);
    }
    hits.sort((x, y) => y[0] - x[0]);
    document.getElementById("sp").textContent = hits.length + (hits.length === 1 ? " article" : " articles") + " found.";
    document.getElementById("results").innerHTML = hits.slice(0, 200).map(([, a]) =>
      `<article class="item noimg"><div><div class="kicker">${esc(a.i)}</div><h3><a href="${a.u}">${esc(a.t)}</a></h3><p>${esc(a.s)}</p></div></article>`).join("");
  }).catch(() => { document.getElementById("sp").textContent = "Search didn't load. Reload the page to try again."; });
})();
</script>"""
    page("/search/", "Search", "Search every article in the Free New York archive.", body, ld=[crld], noindex=True, scripts=js)


def render_404():
    body = ('<div class="pagehead"><h1>Page not found</h1><p>That address doesn\'t match anything in the archive. '
            'Try the search box, <a href="/issues/">browse all issues</a> or go to the <a href="/">latest articles</a>.</p></div>')
    page("/404.html", "Page not found", "This page doesn't exist.", body, noindex=True)


# ---------------------------------------------------------------- machine-readable files
def write_files():
    w = lambda name, text: open(os.path.join(DIST, name), "w").write(text)
    # sitemap
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm in SITEMAP:
        sm.append(f"<url><loc>{e(u)}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>")
    sm.append("</urlset>")
    w("sitemap.xml", "\n".join(sm) + "\n")
    # robots
    if CFG["indexable"]:
        bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot", "PerplexityBot",
                "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot", "Amazonbot", "Bytespider", "meta-externalagent", "DuckAssistBot"]
        robots = "# Search engines and AI assistants are welcome to read and cite this archive.\n" + "".join(
            f"User-agent: {b}\nAllow: /\n\n" for b in bots) + "User-agent: *\nAllow: /\nDisallow: /search/\n\n" + f"Sitemap: {BASE}/sitemap.xml\n"
    else:
        robots = "User-agent: *\nDisallow: /\n"
    w("robots.txt", robots)
    # atom feed
    feed = [a for a in ORDER if a["kind"] in FEED_KINDS][:50]
    entries = "".join(
        f"<entry><title>{e(a['title'])}</title><link href=\"{abs_(a['url'])}\"/><id>{abs_(a['url'])}</id>"
        f"<updated>{a['date']}T00:00:00Z</updated><published>{a['date']}T00:00:00Z</published>"
        + (f"<author><name>{e(a['author'])}</name></author>" if a.get("author") else "")
        + f"<summary>{e(describe(a))}</summary>" + "".join(f'<category term="{e(t)}"/>' for t in a["tags"]) + "</entry>" for a in feed)
    w("feed.xml", f'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>{e(CFG["site_name"])}</title>'
      f'<subtitle>{e(CFG["description"])}</subtitle><link href="{BASE}/"/><link rel="self" href="{BASE}/feed.xml"/><id>{BASE}/</id>'
      f'<updated>{NOW}</updated><author><name>{e(CFG["publisher"])}</name></author>{entries}</feed>\n')
    # llms.txt
    L = [f"# {CFG['site_name']}", "", f"> {CFG['description']}", "",
         f"{CFG['periodical']} is the official newsletter of the {CFG['publisher']} ({CFG['publisher_url']}). This site transcribes "
         f"{len(D['issues'])} issues ({D['issues'][-1]['label']} to {D['issues'][0]['label']}) from PDFs archived on LPedia. Each article page "
         f"has a Markdown copy at its address plus index.md, and cites its original PDF page. The full text of everything is in {BASE}/llms-full.txt.", "",
         "## Key pages", f"- [All issues]({BASE}/issues/): every issue with its contents", f"- [Topics, counties and authors]({BASE}/topics/)",
         f"- [County affiliates]({BASE}/county-affiliates/): monthly meeting times and contacts for LPNY county parties",
         f"- [LPNY updates]({BASE}/updates/): monthly party business round-ups", f"- [About]({BASE}/about/): sources, method and older issues back to 1972", ""]
    for i in D["issues"]:
        L.append(f"## {i['label']}" + (f" (Vol. {i['volume']}, No. {i['number']})" if i.get("volume") else ""))
        for s in i["articles"]:
            a = BY_SLUG[s]
            if a["kind"] == "ad":
                continue
            by = f" By {a['author']}." if a.get("author") else ""
            L.append(f"- [{a['title']}]({abs_(a['url'])}index.md): {a.get('summary') or describe(a)}{by}")
        L.append("")
    w("llms.txt", "\n".join(L))
    full = [f"# {CFG['site_name']}: full text", "", f"> {CFG['description']}", "",
            f"Source: {BASE}/ . Generated {NOW[:10]}. Each article below starts with its title, issue, author, web address and original PDF.", ""]
    for a in ORDER:
        if a["kind"] == "ad":
            continue
        full += ["---", "", article_md(a)]
    w("llms-full.txt", "\n".join(full))
    # headers for Cloudflare static assets
    w("_headers", "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/img/*\n  Cache-Control: public, max-age=31536000, immutable\n"
      "/*.md\n  Content-Type: text/markdown; charset=utf-8\n  X-Robots-Tag: noindex\n/llms*.txt\n  Content-Type: text/plain; charset=utf-8\n"
      "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    w("favicon.svg", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#2b2b2c"/>'
      '<rect y="52" width="64" height="12" fill="#e3c000"/><text x="32" y="42" font-family="Georgia,serif" font-weight="700" font-size="30" '
      'text-anchor="middle" fill="#fff">FNY</text></svg>')


def main():
    global OG_DEFAULT
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "assets"))
    shutil.copytree(os.path.join(ROOT, "site/img"), os.path.join(DIST, "img"))
    open(os.path.join(DIST, "assets/site.css"), "w").write(CSS)
    OG_DEFAULT = make_og_default()
    render_home()
    render_issues()
    for a in ARTS:
        render_article(a)
    listing("/county-affiliates/", "County affiliates", "Each issue's County Affiliate News: meeting times, places and contacts for every LPNY county affiliate.",
            [a for a in ORDER if a["kind"] == "county-news"], nav="county")
    listing("/updates/", "LPNY updates", "The monthly round-ups of party business from the LPNY Secretary and Chair.",
            [a for a in ORDER if a["kind"] == "updates"], nav="updates")
    render_taxonomies()
    render_about()
    render_search()
    render_404()
    write_files()
    n = sum(len(f) for _, _, f in os.walk(DIST))
    size = sum(os.path.getsize(os.path.join(r, x)) for r, _, f in os.walk(DIST) for x in f)
    print(f"dist/: {n} files, {size / 1e6:.1f} MB, {len(SITEMAP)} URLs in sitemap, base {BASE}")


OG_DEFAULT = None
if __name__ == "__main__":
    main()
