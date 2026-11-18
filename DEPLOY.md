# Deploying the Free New York archive

The site is plain static files in `dist/`, served by a Cloudflare Worker with static assets
(`wrangler.jsonc`). No server code runs. It fits easily in the free plan: about 1,060 files and 34 MB,
against limits of 20,000 files and 25 MB per file, with no charge for static requests.

## Interim: the pruvn Cloudflare account

`wrangler.jsonc` names no account, so this public repo doesn't carry one. Choose the account at deploy
time with `CLOUDFLARE_ACCOUNT_ID` (Cloudflare dashboard → Workers & Pages → Account ID), or pick it when
wrangler asks. `site.config.json` assumes the address `https://freeny-archive.devin-31f.workers.dev`.

1. Rebuild and check:
   ```bash
   cd ~/Antigravity/lpny/freeny-site
   python3 tools/build.py && python3 tools/render.py && python3 tools/check_dist.py
   ```
2. Sign in to Cloudflare as a user of the pruvn account (this opens a browser):
   ```bash
   npx wrangler@4 login
   npx wrangler@4 whoami
   ```
3. Deploy:
   ```bash
   CLOUDFLARE_ACCOUNT_ID=<account id> npx wrangler@4 deploy
   ```
   Wrangler prints the live address. If it isn't `freeny-archive.devin-31f.workers.dev`, put the
   printed address in `site.config.json` → `site_url`, then repeat steps 1 and 3. Canonical links,
   the sitemap, `llms.txt` and the feed all use that address.
4. Check the live site: open an article, try the search, and confirm `/robots.txt`, `/sitemap.xml`
   and `/llms.txt` load. A made-up address should show the archive's "Page not found" page.
5. Tell search engines (optional but recommended):
   - Google Search Console: add the site (URL-prefix property), verify it, and submit `/sitemap.xml`.
   - Bing Webmaster Tools: import from Search Console or add the site the same way. Bing's index also
     feeds ChatGPT search and Copilot.

### Optional: a nicer interim address
Instead of `workers.dev`, the Worker can answer on a subdomain of a domain in the pruvn account (for
example `freeny.itspruvn.com`). In the Cloudflare dashboard go to Workers & Pages → freeny-archive →
Settings → Domains & Routes → Add custom domain. Then set `site_url` to it, rebuild and redeploy.

### Check the AI-crawler settings
A `workers.dev` address has no zone settings, so nothing blocks crawlers. On a custom domain, check the
zone's **Security → Bots** settings first. "Block AI bots" (on by default for many zones), Bot Fight
Mode and Cloudflare's managed robots.txt can all keep AI crawlers out, and that overrides this site's
`robots.txt`, which welcomes them. For this site, turn "Block AI bots" off, or limit it to other
hostnames, and leave the managed robots.txt off.

## Later: moving to an lpny.org address

1. In the LPNY Cloudflare account, deploy the same project with `CLOUDFLARE_ACCOUNT_ID` set to that
   account. Set `site_url` (e.g. `https://archive.lpny.org`), rebuild, `npx wrangler@4 deploy`,
   then add the custom domain to the Worker.
2. On the lpny.org zone, let crawlers reach the archive hostname: allow AI crawlers there, and skip Bot
   Fight Mode / Super Bot Fight Mode for that hostname with a WAF custom rule (Skip action).
3. Send the old address to the new one, so search rankings carry over. Replace the interim Worker with
   a one-line redirect Worker:
   ```js
   export default { fetch: (req) => { const u = new URL(req.url); return Response.redirect("https://archive.lpny.org" + u.pathname + u.search, 301); } };
   ```
4. In Search Console, add the new address and use **Change of Address** if both were verified.

## Updating the site later
- Fix a split or a title: edit `data/segments/YYYY-MM.json`, then rebuild and deploy.
- Add a new issue: put the PDF in `source-pdfs/` as `YYYY-MM.pdf`, run `python3 tools/extract.py YYYY-MM`,
  segment it into `data/segments/YYYY-MM.json` following `tools/SEGMENTING.md` (Claude can do this),
  confirm `python3 tools/check_segments.py YYYY-MM` prints OK, then rebuild and deploy.
