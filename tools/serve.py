"""Local preview: serves site/ and wraps index.html in the same skeleton the artifact host adds."""
import http.server, os, functools
SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
HEAD = b'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            body = HEAD + open(os.path.join(SITE, "index.html"), "rb").read() + b"</html>"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            super().do_GET()
http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(H, directory=SITE)).serve_forever()
