import fitz,sys,collections
d=fitz.open(sys.argv[1])
c=collections.Counter()
for p in d:
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines",[]):
            for s in l["spans"]:
                c[(s["font"],round(s["size"],1))]+=len(s["text"])
for k,v in c.most_common(40): print(v,k)
