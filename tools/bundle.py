"""Make one self-contained HTML file (data + downsized photos inlined) for sharing or offline viewing."""
import base64, io, json, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(ROOT, "site/data.json")))
cache = {}
def inline(src):
    if not src: return src
    if src not in cache:
        im = Image.open(os.path.join(ROOT, "site", src)).convert("RGB")
        im.thumbnail((720, 720))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=62, optimize=True)
        cache[src] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return cache[src]
for a in data["articles"]:
    for b in a["body"]:
        if b["t"] == "img": b["src"] = inline(b["src"])
    a["lead"] = inline(a["lead"])
for i in data["issues"]:
    i["cover"] = inline(i["cover"])
page = open(os.path.join(ROOT, "site/index.html")).read()
script = "<script>window.FREENY_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";</script>\n"
i = page.index("<script>")
html = "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><style>body{margin:0}img{max-width:100%}</style>" + page[:i] + script + page[i:] + "</html>"
out = os.path.join(ROOT, "free-new-york-archive.html")
open(out, "w").write(html)
print(out, round(os.path.getsize(out) / 1e6, 1), "MB")
