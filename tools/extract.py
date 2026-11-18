"""Stage 1: pull text blocks and photos out of each Free New York PDF.

For every source-pdfs/YYYY-MM.pdf writes:
  data/blocks/YYYY-MM.json  - every text block (id, page, bbox, font, size, text) + images
  data/dumps/YYYY-MM.txt    - compact human/LLM-readable dump used to segment articles
  site/img/YYYY-MM/*.jpg    - photos (logos repeated across many issues are dropped)
"""
import fitz, json, hashlib, io, os, re, sys, collections
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source-pdfs")
OUT_B, OUT_D = os.path.join(ROOT, "data/blocks"), os.path.join(ROOT, "data/dumps")
OUT_I = os.path.join(ROOT, "site/img")
for p in (OUT_B, OUT_D, OUT_I):
    os.makedirs(p, exist_ok=True)

MIN_IMG = 90          # points; smaller placed images are icons/ornaments
MAX_IMG_PX = 1400


def line_text(line):
    return "".join(s["text"] for s in line["spans"])


def block_text(b):
    """Join a block's lines, undoing InDesign soft-hyphen line breaks."""
    out = ""
    for l in b["lines"]:
        t = line_text(l)
        if not t.strip():
            continue
        if out.endswith("\xad"):
            out = out[:-1] + t.lstrip()
        elif out.endswith("-") and not out.endswith(" -"):
            out = out + t.lstrip()
        elif out:
            out = out.rstrip() + " " + t.lstrip()
        else:
            out = t
    return re.sub(r"[ \t]+", " ", out.replace("\xad", "")).strip()


def line_style(l):
    c = collections.Counter()
    for s in l["spans"]:
        c[(s["font"], round(s["size"]))] += len(s["text"].strip())
    return c.most_common(1)[0][0] if c else None


def split_block(b):
    """PyMuPDF sometimes merges separate InDesign frames (a headline and body text,
    a TOC and the masthead) into one block. Split where the line style changes or
    the lines stop touching."""
    groups, cur, prev = [], [], None
    for l in b["lines"]:
        if not line_text(l).strip():
            continue
        st = line_style(l)
        if prev is not None:
            pst, pb = prev
            gap = l["bbox"][1] - pb[3]
            lh = pb[3] - pb[1]
            no_overlap = l["bbox"][0] > pb[2] or l["bbox"][2] < pb[0]
            if (st[1] != pst[1] or st[0].split("-")[0] != pst[0].split("-")[0]) and (gap > 2 or abs(st[1] - pst[1]) > 2) \
                    or gap > max(lh * 1.6, 14) or (no_overlap and gap > -lh * 0.5) or gap < -lh * 1.5:
                groups.append(cur)
                cur = []
        cur.append(l)
        prev = (st, l["bbox"])
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        x0 = min(l["bbox"][0] for l in g); y0 = min(l["bbox"][1] for l in g)
        x1 = max(l["bbox"][2] for l in g); y1 = max(l["bbox"][3] for l in g)
        out.append(dict(type=0, lines=g, bbox=(x0, y0, x1, y1)))
    return out


def dominant(b):
    c = collections.Counter()
    for l in b["lines"]:
        for s in l["spans"]:
            c[(s["font"], round(s["size"], 1))] += len(s["text"].strip())
    (font, size), _ = c.most_common(1)[0]
    return font, size


def issue(fname, seen_hashes):
    key = fname[:-4]
    doc = fitz.open(os.path.join(SRC, fname))
    blocks, images = [], []
    for pno, page in enumerate(doc, 1):
        n = 0
        raw = [s for b in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_PRESERVE_LIGATURES)["blocks"]
               if b["type"] == 0 for s in split_block(b)]
        for b in raw:
            t = block_text(b)
            if not t:
                continue
            font, size = dominant(b)
            bold = any(k in font for k in ("Bold", "Black", "Heavy"))
            italic = "Italic" in font
            lines = [re.sub(r"[ \t]+", " ", line_text(l).replace("\xad", "")).strip() for l in b["lines"]]
            blocks.append(dict(id=f"p{pno}b{n}", page=pno, bbox=[round(v) for v in b["bbox"]],
                               font=font, size=size, bold=bold, italic=italic, text=t,
                               lines=[x for x in lines if x],
                               hyph_end=line_text(b["lines"][-1]).rstrip().endswith("\xad"),
                               lmeta=[[round(l["bbox"][0]), round(l["bbox"][2]),
                                       all(any(k in s["font"] for k in ("Bold", "Black", "Heavy")) for s in l["spans"] if s["text"].strip()),
                                       line_text(l).rstrip().endswith("\xad")]
                                      for l in b["lines"] if line_text(l).strip()]))
            n += 1
        k = 0
        for info in page.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            if (x1 - x0) < MIN_IMG or (y1 - y0) < MIN_IMG or not info["xref"]:
                continue
            try:
                pix = fitz.Pixmap(doc, info["xref"])
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            except Exception:
                # fall back to rendering the region of the page
                im = Image.open(io.BytesIO(page.get_pixmap(clip=fitz.Rect(info["bbox"]), dpi=200).tobytes("png"))).convert("RGB")
            h = hashlib.md5(im.resize((16, 16)).tobytes()).hexdigest()
            seen_hashes[h].add(key)
            im.thumbnail((MAX_IMG_PX, MAX_IMG_PX))
            iid = f"p{pno}i{k}"
            k += 1
            images.append(dict(id=iid, page=pno, bbox=[round(v) for v in info["bbox"]], hash=h,
                               w=im.width, h=im.height, file=f"img/{key}/{iid}.jpg", _im=im))
    return key, doc.page_count, blocks, images


def dump(key, pages, blocks, images):
    lines = [f"# ISSUE {key}  ({pages} pages)", ""]
    for pno in range(1, pages + 1):
        lines.append(f"=== PAGE {pno} ===")
        items = [("b", b) for b in blocks if b["page"] == pno] + [("i", i) for i in images if i["page"] == pno]
        items.sort(key=lambda it: (it[1]["bbox"][1] // 40, it[1]["bbox"][0]))
        for kind, it in items:
            x0, y0, x1, y1 = it["bbox"]
            if kind == "i":
                lines.append(f"[{it['id']}] IMAGE at x{x0}-{x1} y{y0}-{y1}")
                continue
            style = f"{it['font']} {it['size']:g}"
            txt = it["text"] if len(it["text"]) < 260 else it["text"][:180] + " … " + it["text"][-60:]
            lines.append(f"[{it['id']}] ({style}; x{x0}-{x1} y{y0}-{y1}) {txt}")
        lines.append("")
    return "\n".join(lines)


def main():
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".pdf"))
    if len(sys.argv) > 1:
        files = [f for f in files if f[:-4] in sys.argv[1:]]
    seen = collections.defaultdict(set)
    results = [issue(f, seen) for f in files]
    for key, pages, blocks, images in results:
        kept = []
        os.makedirs(os.path.join(OUT_I, key), exist_ok=True)
        for im in images:
            if len(seen[im["hash"]]) > 2:      # masthead/logo reused across issues
                continue
            im.pop("_im").save(os.path.join(ROOT, "site", im["file"]), "JPEG", quality=82, optimize=True)
            kept.append(im)
        for im in images:
            im.pop("_im", None)
        json.dump(dict(issue=key, pages=pages, blocks=blocks, images=kept),
                  open(os.path.join(OUT_B, key + ".json"), "w"), ensure_ascii=False, indent=1)
        open(os.path.join(OUT_D, key + ".txt"), "w").write(dump(key, pages, blocks, kept))
        print(key, pages, "pages", len(blocks), "blocks", len(kept), "images")


if __name__ == "__main__":
    main()
