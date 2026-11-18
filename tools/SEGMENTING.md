# Splitting a Free New York issue into articles

Input for issue `YYYY-MM`:
- `data/dumps/YYYY-MM.txt`: every text block and photo, page by page. Each line is
  `[id] (font size; x-range y-range) text`. Text longer than 260 characters is shortened with
  ` … ` in the dump. Pages are 612×792 points, usually with 3 columns at x≈36–211, 220–395 and 404–579.
- `data/blocks/YYYY-MM.json`: the same blocks with full text, if you need it.

Output: `data/segments/YYYY-MM.json`, which assigns **every block id to an article or to `skip`**.
The site builder assembles the text from the blocks, so you never retype article text. You only
group and order block ids.

```json
{
  "issue": "2025-07",
  "volume": 54, "number": 7,
  "articles": [
    {
      "title": "Ed Clark 1930–2025",
      "subtitle": null,
      "author": "Christopher Skelly",
      "author_role": "Communications Director, Brooklyn Chair",
      "kind": "article",
      "tags": ["obituary", "party history"],
      "counties": [],
      "summary": "One sentence, under 30 words, in plain language.",
      "title_blocks": ["p1b3", "p1b4"],
      "byline_blocks": [],
      "body": [
        {"type": "p", "blocks": ["p1b0", "p1b1"]},
        {"type": "p", "blocks": ["p1b2", "p1b10"]},
        {"type": "h", "blocks": ["p2b11"]},
        {"type": "image", "id": "p1i0", "caption_blocks": []},
        {"type": "quote", "blocks": ["p4b3"]},
        {"type": "list", "blocks": ["p5b1", "p5b2"]}
      ]
    }
  ],
  "skip": ["p1b6", "p1b7", "p1b8"]
}
```

## Rules
- **Every block id in the dump appears exactly once**: in an article's `title_blocks`,
  `byline_blocks`, a body item's `blocks` / `caption_blocks`, or `skip`. Image ids are optional
  (leave out logos, ornaments and ads you don't want shown).
- **Body order is reading order.** Articles flow down a column, then to the top of the next column,
  and jump pages ("continued on page 2" … "continued from page 1"). Follow that flow, not the order
  of lines in the dump.
- **One `p` item is one paragraph.** A column break often falls mid-sentence. If a block ends
  without closing punctuation and the next block in reading order continues the sentence, put both
  ids in the same `p` item. Also merge words split across blocks (for example "Babi" + "lon, …").
- `h` is a subheading inside an article (bold 11–12pt lines such as "Ballot Access Bills").
  `quote` is a pull quote. `list` holds blocks that are list or directory lines; each block becomes one line.
- **skip:** the masthead ("Free New York", "The Official Newsletter…", volume/date line), page
  footers ("JULY 2025 | 1", "2 | FREE NEW YORK"), the table of contents, "(continued on/from page N)",
  and duplicated pull quotes that repeat body text.
- **kind** is one of:
  - `article` (news, features, op-eds, obituaries, event recaps)
  - `updates` (an "LPNY Updates" or "Updates from the Chair" round-up)
  - `county-news` (the "County Affiliate News" pages; make ONE article for the whole section, and
    use `h` for each county name)
  - `directory` (the officer / contact directory, usually the last page)
  - `ad` (donation asks, membership forms, event flyers, merchandise)
  - `other`
- Use the **title** as printed, in normal title case ("Matthew Morgan Wins Spot on Ballot", not
  all caps). Put a two-line headline's second line in `subtitle` only when it reads as a separate
  dek; otherwise join both lines into the title.
- If a piece has no printed headline (an ad or a boxed notice), write a short plain title for it and
  leave `title_blocks` empty.
- **author / author_role:** take them from the byline ("by Daniel Castello / LPNY Vice-Chair /
  Onondaga County Vice-Chair" → author "Daniel Castello", role "LPNY Vice-Chair, Onondaga County
  Vice-Chair"). Use `null` when there is no byline.
- **tags:** 1–4 lowercase topics, reused across issues where possible: `elections`, `candidates`,
  `ballot access`, `legislation`, `party business`, `convention`, `events`, `podcast`, `obituary`,
  `party history`, `policy`, `fundraising`, `county affiliates`, `national party`, `opinion`.
- **counties:** the NY counties or boroughs the article is about, e.g. `["Monroe"]`. Leave it empty for statewide pieces.
- **summary:** one plain sentence for the article list. Base it on the text and invent nothing.
- If an image's caption is a separate block, list it in `caption_blocks`.

A finished example is in `data/segments/2025-07.json`. Compare it with `data/dumps/2025-07.txt` before you start.

When you finish, run `python3 tools/check_segments.py YYYY-MM` from the `freeny-site` folder. It
must print `OK`. Fix any missing or duplicate ids it reports.
