# Free New York archive site

A static website built from the 41 PDF issues of *Free New York* (LPNY's newsletter), January 2023 to October 2026, hosted on LPedia.

## How it's built
1. `source-pdfs/`: the original PDFs, downloaded from LPedia's media bucket (`urls.txt`).
2. `python3 tools/extract.py`: pulls every text block (with font, position and line breaks) and every photo out of each PDF. Writes `data/blocks/`, `data/dumps/` and `site/img/`. Block ids are stable between runs.
3. `data/segments/YYYY-MM.json`: which blocks form which article, in reading order, plus title, author, tags, counties and a one-line summary. These were written by Claude agents following `tools/SEGMENTING.md`, and `python3 tools/check_segments.py` confirms every block is used exactly once. Hand-edit these files to fix a split.
4. `python3 tools/build.py`: assembles the article text (rejoins hyphenated and column-split words, splits merged paragraphs) into `site/data.json`.
5. `python3 tools/render.py`: writes the public website to `dist/`. Every article, issue, topic, county and author gets its own page with
   canonical URL, Open Graph tags and schema.org JSON-LD, plus `sitemap.xml`, `robots.txt` (search and AI crawlers welcome), `feed.xml`,
   `llms.txt`, `llms-full.txt` and a Markdown copy of every article (`…/index.md`). Settings such as the site address live in `site.config.json`.
   `python3 tools/check_dist.py` checks every page for broken links, missing metadata and invalid structured data.
6. Deploy `dist/` to Cloudflare: see [DEPLOY.md](DEPLOY.md).
7. `site/index.html` is the earlier one-page version, still used by `python3 tools/bundle.py`: writes `free-new-york-archive.html`, one self-contained file with the data and smaller photos inlined, for sharing or viewing offline.

Preview the public site locally with `python3 -m http.server 8767 --directory dist`.

## Known limits
- Text comes from the PDFs' text layer. Typos in the original are kept, except a few headline typos that the agents corrected.
- Full-page flyers and ads that are only images have a title but no text.
- Some image-only pages were titled from each issue's table of contents.
