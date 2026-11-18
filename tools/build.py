"""Stage 3: assemble articles from blocks + segments into site/data.json."""
import json, os, re, sys, unicodedata, calendar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_BASE = "https://mywikis-wiki-media.s3.us-central-1.wasabisys.com/lpedia/LPNY_NEWSLETTERS_{}.pdf"
SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs", "via", "with", "from"}
KEEP_UPPER = {"LPNY", "LP", "NY", "NYC", "LNC", "US", "USA", "II", "III", "IV", "EC", "GOP", "PAC", "FAQ", "LPQC",
              "A3312", "S01870", "A02724", "NYS", "DC", "AI", "TV", "SUNY", "CUNY", "ID", "CEO", "LPMC", "BOE"}


AUTHOR_ALIASES = {"Andrew M. Kolstee": "Andrew Kolstee", "Vincent O'Neill": "Vincent O\u2019Neill",
                  "Richard Purtell": "Rich Purtell", "E. Rose Leatherman": "Rose Leatherman"}


def slugify(s, n=70):
    s = re.sub(r"[\u2010-\u2015\u2212/]", " ", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:n].rstrip("-") or "untitled"


def titlecase(s):
    """Title-case text that was printed in all caps; leave mixed-case text alone."""
    letters = [c for c in s if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return s
    words = s.split(" ")
    out = []
    for i, w in enumerate(words):
        core = re.sub(r"[^A-Za-z0-9]", "", re.sub(r"['’]S$", "", w))
        if core.upper() in KEEP_UPPER or re.fullmatch(r"[A-Z]\d+|\d+[A-Z]*", core or "x"):
            out.append(re.sub(r"(['’])S$", r"\1s", w))
        elif i and core.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(out)


def tidy(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    return t


def join_blocks(bs):
    out = ""
    for b in bs:
        t = b["text"].strip()
        if not out:
            out = t
        elif prev_h:
            out += t
        elif out.endswith("-") and not out.endswith(" -") and t[:1].isalnum():
            out += t
        else:
            out = glue(out, t)
        prev_h = b.get("hyph_end")
    if not bs:
        return ""
    return tidy(out)


try:
    WORDS = set(w.strip().lower() for w in open("/usr/share/dict/words"))
except OSError:
    WORDS = set()


def glue(a, b):
    """Join two text runs. Drop the space when the runs split one word across a column
    break ("na" + "tional" -> "national"), judged against the system word list."""
    m1 = re.search(r"([A-Za-z]+)$", a); m2 = re.match(r"([a-z]+)", b)
    if m1 and m2 and WORDS:
        x, y = m1.group(1).lower(), m2.group(1)
        if (x + y) in WORDS and not (x in WORDS and y in WORDS):
            return a + b
    return a + " " + b


def unspace(t):
    toks = t.split(" ")
    if len(toks) > 8 and sum(len(x) <= 2 for x in toks) / len(toks) > 0.85:
        return t.replace(" ", "")
    return t


def merge_broken(body):
    """Rejoin paragraphs that were cut mid-sentence (the next one starts in lower case)."""
    out = []
    for b in body:
        prev = out[-1] if out else None
        if (prev and prev["t"] == "p" and b["t"] == "p" and b["text"][:1].islower()
                and not re.search(r"[.!?:]$", prev["text"]) and not re.match(r"(https?:|www\.|\S+\.(org|com|us)\b|\S+@)", b["text"])):
            prev["text"] = glue(prev["text"], b["text"])
            continue
        out.append(b)
    return out


END_PUNCT = tuple('.!?:"\u201d\u2019)')


def split_paragraphs(bs):
    """Turn the blocks of one agent-made paragraph into one or more items. Blocks sometimes
    hold several printed paragraphs, or a bold subheading, run together; split those on a
    first-line indent, a short last line, or a line set entirely in bold."""
    items, cur = [], ""
    def add(t, hyph):
        nonlocal cur
        if not cur:
            cur = t
        elif hyph:
            cur += t
        elif cur.endswith("-") and not cur.endswith(" -") and t[:1].isalnum():
            cur += t
        else:
            cur = glue(cur, t)
    def flush():
        nonlocal cur
        if cur.strip():
            items.append(("p", unspace(tidy(cur))))
        cur = ""
    prev_hyph = False
    for b in bs:
        meta = b.get("lmeta") or [[0, 0, False, False]] * len(b["lines"])
        left = min(m[0] for m in meta); right = max(m[1] for m in meta)
        block_bold = sum(m[2] for m in meta) > len(meta) / 2
        for i, (line, m) in enumerate(zip(b["lines"], meta)):
            x0, x1, bold, hyph = m
            starts_fresh = (not cur) or cur.rstrip().endswith(END_PUNCT)
            nxt = b["lines"][i + 1] if i + 1 < len(b["lines"]) else ""
            if (bold and not block_bold and len(line) < 80 and not prev_hyph and not hyph and starts_fresh
                    and not line.rstrip().endswith(",") and (not nxt or not nxt[:1].islower())):
                flush(); items.append(("h", tidy(line))); prev_hyph = False; continue
            if i and cur and not prev_hyph:
                pl, pm = b["lines"][i - 1], meta[i - 1]
                ends = pl.rstrip().endswith(END_PUNCT)
                if ends and (x0 > left + 6 or pm[1] < right - 30):
                    flush()
            add(line.strip(), prev_hyph)
            prev_hyph = hyph
    flush()
    return items


def list_lines(bs):
    lines, hy = [], False
    for b in bs:
        meta = b.get("lmeta") or [[0, 0, False, False]] * len(b["lines"])
        for l, m in zip(b["lines"], meta):
            if lines and hy:
                lines[-1] = lines[-1] + l
            else:
                lines.append(l)
            hy = m[3]
    return [tidy(l) for l in lines if l.strip()]


def build():
    issues, articles = [], []
    used_slugs = set()
    for f in sorted(os.listdir(os.path.join(ROOT, "data/segments"))):
        key = f[:-5]
        seg = json.load(open(os.path.join(ROOT, "data/segments", f)))
        blk = json.load(open(os.path.join(ROOT, "data/blocks", key + ".json")))
        B = {b["id"]: b for b in blk["blocks"]}
        I = {i["id"]: i for i in blk["images"]}
        y, m = map(int, key.split("-"))
        iss = dict(key=key, year=y, month=m, label=f"{calendar.month_name[m]} {y}",
                   volume=seg.get("volume"), number=seg.get("number"), pages=blk["pages"],
                   pdf=PDF_BASE.format(key), articles=[])
        for a in seg["articles"]:
            title = tidy(titlecase(a.get("title") or "Untitled"))
            base = f"{key}-{slugify(title, 60)}"
            slug, n = base, 2
            while slug in used_slugs:
                slug, n = f"{base}-{n}", n + 1
            used_slugs.add(slug)
            body, pages, words = [], set(), 0
            for it in a.get("body", []):
                t = it.get("type")
                if t == "image":
                    im = I.get(it.get("id"))
                    if not im:
                        continue
                    cap = join_blocks([B[c] for c in it.get("caption_blocks", []) if c in B])
                    body.append(dict(t="img", src=im["file"], w=im["w"], h=im["h"], cap=cap or None))
                    pages.add(im["page"])
                    continue
                bs = [B[i] for i in it.get("blocks", []) if i in B]
                if not bs:
                    continue
                pages.update(b["page"] for b in bs)
                if t == "list":
                    lines = list_lines(bs)
                    body.append(dict(t="list", lines=lines))
                    words += sum(len(l.split()) for l in lines)
                elif t == "h":
                    body.append(dict(t="h", text=titlecase(join_blocks(bs))))
                elif t == "quote":
                    txt = join_blocks(bs)
                    body.append(dict(t="quote", text=txt))
                    words += len(txt.split())
                else:
                    for kind, txt in split_paragraphs(bs):
                        if kind == "h":
                            body.append(dict(t="h", text=titlecase(txt)))
                            continue
                        if len(txt) < 140 and txt.isupper():
                            txt = titlecase(txt)
                        body.append(dict(t="p", text=txt))
                        words += len(txt.split())
            pages.update(B[i]["page"] for i in a.get("title_blocks", []) if i in B)
            body = merge_broken(body)
            lead = next((x["src"] for x in body if x["t"] == "img"), None)
            art = dict(slug=slug, issue=key, title=title,
                       subtitle=tidy(titlecase(a["subtitle"])) if a.get("subtitle") else None,
                       author=AUTHOR_ALIASES.get(a.get("author"), a.get("author")), role=a.get("author_role"), kind=a.get("kind", "article"),
                       tags=sorted(set(t.lower() for t in a.get("tags", []))),
                       counties=sorted(set(a.get("counties", []))), summary=a.get("summary"),
                       pages=sorted(pages), words=words, lead=lead, body=body)
            articles.append(art)
            iss["articles"].append(slug)
        iss["cover"] = next((x["lead"] for x in articles if x["issue"] == key and x["lead"]), None)
        issues.append(iss)
    issues.sort(key=lambda i: i["key"], reverse=True)
    data = dict(title="Free New York", issues=issues, articles=articles)
    out = os.path.join(ROOT, "site/data.json")
    json.dump(data, open(out, "w"), ensure_ascii=False, separators=(",", ":"))
    kinds = {}
    for a in articles:
        kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
    print(f"{len(issues)} issues, {len(articles)} articles {kinds}, {os.path.getsize(out)//1024} KB")


if __name__ == "__main__":
    build()
