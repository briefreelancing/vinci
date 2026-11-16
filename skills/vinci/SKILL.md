---
name: vinci
description: Turn keyword research and site crawl exports into work a content team can act on. Groups a keyword list (Semrush, Ahrefs, Google Keyword Planner, Search Console queries) into topics and writes one content brief per topic for writers. Audits page titles and meta descriptions from a crawl (Screaming Frog, Sitebulb, any URL and title sheet), optionally prioritized with Search Console data, and writes length-checked rewrites in a review sheet for sign-off. Use when someone uploads a keyword list or crawl export and asks for content briefs, a content plan, keyword clustering, keyword mapping, title tag or meta description rewrites, or on-page metadata fixes.
---

# Vinci

Turns an SEO strategist's raw exports into two things other people can use:

- **Content briefs** for writers, one per topic, from a keyword list.
- **A title and description review sheet** for whoever approves on-page changes, from a site crawl.

With both a keyword list and a crawl, the two connect: each topic is matched to the page that
should carry it, and that page's title is checked against the topic's main keyword.

**Core rule: the script calculates, you write.** Grouping, demand totals, lengths, duplicates and
priorities come from `vinci.py`. You write the briefs and the new titles. `vinci.py` refuses to
render anything until your writing agrees with the data: keywords must exist in the topic, numbers
must trace to the data, titles and descriptions must fit, and no two pages may share a title.

## What the user provides

Native exports, exactly as downloaded. Any subset works. Upload everything together.

| File | Gives | Recognized by |
|---|---|---|
| Keyword list | Briefs | A keyword column, ideally with search volume. Difficulty, intent, position and URL are used when present. |
| Site crawl | Title and description audit | A URL column and a title column |
| Search Console pages export | Priority order and click rate check | Page, clicks, impressions |
| Page and query pairs | Each page's top queries | Page, query, clicks. Only available from the Search Console API, Looker Studio or a Sheets add-on, not the standard export. |

How to get each file: `references/exporting-data.md`. Menu paths there may have changed; say so if
a step doesn't match what the user sees.

## Workflow

1. **Run the analysis** on everything uploaded. Only `openpyxl` is needed, and only for reading
   `.xlsx` inputs and writing the Excel review sheet; install it if missing.

   ```bash
   python <this-skill-folder>/scripts/vinci.py analyze <files, folders or zips> --out vinci_out \
     --client "Client name" --brand-terms "acme,acme co"
   ```

   Ask for brand terms only if the user hasn't given them and the client name doesn't make them
   obvious. Options: `--briefs 15` (topics in the brief queue), `--rewrites 40` (pages in the
   rewrite queue), `--overlap 0.5` (how many words two keywords must share to be one topic),
   `--merge "keyword a=keyword b"` (join two topics; repeatable).
2. **Read `vinci_out/summary.json`** and tell the user what was read and what was skipped, in two
   or three lines. Then read `clusters.json` and `title_audit.json`, whichever exist.
3. **Look at the topics before writing.** Grouping is by shared words, so synonyms land in
   separate topics (for example "wedding cake prices" and "how much is a wedding cake"). If two
   topics in the queue would clearly be one article, rerun step 1 with `--merge`. If a topic mixes
   unrelated things, rerun with a higher `--overlap`. Tell the user what you merged.
4. **Give the chat summary** (format below) and ask which they want: briefs, title rewrites, or both,
   and how many. Default to the top 5 briefs and the top 10 rewrites if they say "go ahead".
5. **Write briefs** to `vinci_out/briefs.json` following `templates/briefs_template.json`, then:

   ```bash
   python <this-skill-folder>/scripts/vinci.py render-briefs --out vinci_out
   ```

   It prints errors and stops if anything fails the check. Fix and rerun. It writes
   `briefs.html` (the full pack, prints cleanly to PDF) and `briefs/NN-topic.md` (one file per
   writer).
6. **Write rewrites** to `vinci_out/rewrites.json` following `templates/rewrites_template.json`, then:

   ```bash
   python <this-skill-folder>/scripts/vinci.py render-rewrites --out vinci_out
   ```

   It writes `title_review.xlsx` and `title_review.csv`, in priority order, with a column for the
   reviewer's decision.
7. **Send the files** and say in one line what each is for and who it goes to.

## Reading clusters.json

| Key | Meaning |
|---|---|
| `demand_type` | `search volume` (monthly searches) or `impressions` (Search Console queries). Name it correctly; never call impressions "search volume". |
| `brief_queue` | Topic ids in priority order, highest total demand first |
| `clusters[].primary_keyword` | The highest-demand keyword in the topic. The brief's main target. |
| `clusters[].total_demand`, `keyword_count`, `average_difficulty` | Use these as given |
| `clusters[].intent`, `intent_mix_pct` | Dominant intent by demand. `keywords[].intent_source` says whether it came from the export or a word rule. `unclassified` means no rule matched: judge it yourself and say it is your reading. |
| `clusters[].action`, `existing_page` | `refresh existing page` when a page already ranks or matches by title; otherwise `new page`. `matched_by` says how sure the match is. A title match is a suggestion: say so. |
| `clusters[].questions`, `common_modifiers` | Question keywords and frequent extra words, useful for headings |
| `site_urls` | Every page in the crawl. Internal links in a brief must come from this list. |
| `notes` | Data caveats. Mention the ones that affect the plan. |

## Reading title_audit.json

| Key | Meaning |
|---|---|
| `rewrite_queue` | URLs in priority order: most impressions first when Search Console data exists, otherwise most issues first |
| `pages[].issues`, `issue_text` | What is wrong, in code and in plain words |
| `pages[].search_console` | Clicks, impressions, click rate, position, and `band_median_ctr_pct`: this site's typical click rate at similar positions |
| `pages[].target_keyword` | The topic's main keyword when the keyword plan maps a topic to this page. The new title must contain it. |
| `pages[].top_queries` | The page's top queries, when page and query pairs were uploaded |
| `brand_suffix` | The ending most titles share (for example " \| Acme"). Keep it on rewritten titles that had it. |
| `thresholds` | The limits used. Rules of thumb, shown so they can be questioned. |

## Writing briefs

- **One brief per topic in the queue**, in queue order. `cluster_id` and `primary_keyword` must
  match `clusters.json` exactly.
- **`target_keywords`** must be keywords from that topic. Pick the ones a single piece can
  honestly serve, usually 3 to 8. Don't list all of them.
- **`summary` and `search_intent` are fact fields.** Every number in them must be in the data for
  that topic. No mental math, no "roughly", no outside statistics.
- **Do not invent what you cannot see.** You have no search results, competitor pages or word
  counts. Don't recommend a word count, cite a competitor or claim what "top-ranking pages" do. If
  the user wants that, ask them to paste the top results.
- **`search_intent`** says in plain words what the searcher is trying to get done and what would
  satisfy them. Not just the label.
- **`outline`**: 4 to 8 headings a writer can start from, each with a one-line note. Use the
  topic's question keywords as headings where they fit. Headings are suggestions, not facts.
- **`internal_links`**: only URLs from `site_urls`, only when a crawl was uploaded. Otherwise leave
  the list empty.
- **`working_title`** at most 60 characters, **`meta_description`** 70 to 155.
- For a `refresh existing page` topic, say in `writer_notes` that this updates the existing page
  rather than adding a new one, so the site doesn't end up with two pages on the same topic.
- Plain words. Expand jargon on first use. Write for a writer who has never seen a keyword tool.

## Writing rewrites

- **One entry per page** from `rewrite_queue`, with `url`, `new_title`, `new_description` and
  `reason`.
- **`reason`** is one plain sentence for the reviewer: what was wrong and what the change does.
  You may quote numbers from that page's audit entry. Never promise a result ("will increase
  clicks"); say what the change is meant to do.
- **Titles**: 30 to 60 characters including the brand ending. Lead with what the page is about.
  Contain the `target_keyword` when there is one, or the top query when there isn't, in natural
  word order. If the target keyword truly doesn't suit the page, set `keyword_waived` to the reason.
- **Descriptions**: 70 to 155 characters. Say what the reader gets and why to click. Write one
  whenever the page has a description issue.
- **Describe only what the page shows.** You know the page from its URL, current title,
  description and H1. Don't invent prices, offers, counts, dates or claims. If you can't tell what
  a page is for, say so in `reason` and keep the rewrite conservative.
- **Every title and description must be unique** across the site.
- **Low click rate** means low compared with this site's own pages at similar positions. It is a
  reason to look at the title, not proof the title is the cause.

## Chat summary format

```
**What I read:** <files and what each was read as; anything skipped and why>

**Keyword plan:** <keywords> keywords in <clusters> topics. <n> match an existing page, <n> need a new page.
Top topics: <3 to 5 lines: primary keyword, total demand with its type, action>

**Titles and descriptions:** <pages_checked> pages checked, <pages_with_issues> with issues.
<2 to 3 lines: the most common issues, and the highest-traffic page that needs work>

<one line on data caveats from notes>
Which would you like: briefs, title rewrites, or both?
```

Leave out a section if its file wasn't produced, and say what to upload to get it.

## Known limits

- Topics are grouped by shared words, not by which pages rank for them. Synonyms need `--merge`.
- Intent comes from the export when present. Otherwise simple word rules are used and many
  keywords stay `unclassified`.
- Page matching by title is a suggestion. Matching by ranking URL (when the keyword export has
  position and URL columns) is more reliable.
- Length limits are in characters. Search engines cut titles by pixel width, so a title within the
  limit can still be shortened.
- Keyword Planner volume ranges ("1K – 10K") are read as the low end, and this is noted.
- The checks confirm that keywords, numbers, links and lengths are valid. They cannot judge
  whether a brief is good or a title is appealing. Read your work once before sending.
- Numbers must use US formatting (1,234.56).
