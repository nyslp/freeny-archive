"""Check that data/segments/<issue>.json uses every block id exactly once."""
import json, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {"article", "updates", "county-news", "directory", "ad", "other"}
TYPES = {"p", "h", "quote", "list", "image"}


def check(key):
    blocks = json.load(open(os.path.join(ROOT, "data/blocks", key + ".json")))
    ids = {b["id"] for b in blocks["blocks"]}
    imgs = {i["id"] for i in blocks["images"]}
    path = os.path.join(ROOT, "data/segments", key + ".json")
    if not os.path.exists(path):
        return [f"{key}: no segments file"]
    seg = json.load(open(path))
    used = collections.Counter(seg.get("skip", []))
    errs = []
    for a in seg.get("articles", []):
        t = a.get("title") or "?"
        if a.get("kind") not in KINDS:
            errs.append(f"{t}: bad kind {a.get('kind')!r}")
        if not a.get("title"):
            errs.append(f"article with no title (blocks {a.get('title_blocks')})")
        used.update(a.get("title_blocks", []))
        used.update(a.get("byline_blocks", []))
        for it in a.get("body", []):
            if it.get("type") not in TYPES:
                errs.append(f"{t}: bad body type {it.get('type')!r}")
            if it.get("type") == "image":
                if it.get("id") not in imgs:
                    errs.append(f"{t}: unknown image {it.get('id')}")
                used.update(it.get("caption_blocks", []))
            else:
                used.update(it.get("blocks", []))
    missing = sorted(ids - set(used))
    extra = sorted(set(used) - ids)
    dup = sorted(k for k, v in used.items() if v > 1)
    if missing:
        errs.append(f"missing ids: {' '.join(missing)}")
    if extra:
        errs.append(f"unknown ids: {' '.join(extra)}")
    if dup:
        errs.append(f"ids used more than once: {' '.join(dup)}")
    return [f"{key}: {e}" for e in errs]


if __name__ == "__main__":
    keys = sys.argv[1:] or sorted(f[:-5] for f in os.listdir(os.path.join(ROOT, "data/blocks")))
    allerrs = []
    for k in keys:
        allerrs += check(k)
    print("\n".join(allerrs) if allerrs else "OK")
    sys.exit(1 if allerrs else 0)
