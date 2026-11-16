# Getting your files

Vinci reads exports as downloaded. Don't rename columns or delete rows. Menu names change often;
if a step doesn't match what you see, look for the nearest "Export" button.

## Keyword list (for content briefs)

Any one of these works. A keyword column is required; search volume makes the plan much better.

- **Semrush**: Keyword Magic Tool or Keyword Manager > Export > CSV. Columns used: Keyword,
  Intent, Search Volume, Keyword Difficulty. From Organic Research > Positions, Position and URL
  are also used to find the page that already ranks.
- **Ahrefs**: Keywords Explorer > any report > Export. Columns used: Keyword, Volume, KD. From
  Site Explorer > Organic keywords, Current position and Current URL are also used.
- **Google Keyword Planner**: Keyword ideas > Download keyword ideas > .csv. Volume ranges such as
  "1K – 10K" are read as the low end.
- **Search Console**: Performance > Export > the Queries table. Vinci uses impressions as the
  demand number and labels it as impressions, not search volume.
- **Your own list**: a CSV with a `Keyword` column, and optionally `Search Volume`.

## Site crawl (for titles and descriptions)

- **Screaming Frog**: Internal tab > filter HTML > Export. Columns used: Address, Status Code,
  Indexability, Title 1, Meta Description 1, H1-1.
- **Sitebulb**: URL Explorer > Internal HTML > Export. Columns used: URL, Title, Meta Description, H1.
- **Your own sheet**: a CSV with `URL` and `Title` columns, and optionally `Meta Description`, `H1`.

Only pages that return status 200, are HTML and are indexable are checked. The rest are counted
and left out.

## Search Console pages (optional, sets the priority order)

Performance > set the date range (the last 3 months is a good default) > Export. Upload the zip
as is, or just `Pages.csv`. With it, pages are ordered by impressions and click rate is compared
with your own pages at similar positions.

## Page and query pairs (optional)

The standard Search Console export lists pages and queries separately, never together. To get each
page's top queries you need the Search Console API, a Looker Studio table with both Landing Page
and Query, or a Sheets add-on such as Search Analytics for Sheets. Export it as a CSV with page,
query, clicks and impressions columns. Without it, Vinci skips the "title misses top query" check
and says so.
