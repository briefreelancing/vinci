"""Run with `python -m unittest discover tests` or `python -m pytest -q`."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "vinci" / "scripts"
SAMPLE = ROOT / "sample-data" / "northwind-bakery"
EXAMPLE = ROOT / "examples" / "northwind-bakery"
sys.path.insert(0, str(SCRIPTS))

from vinci_core import audit, check, cluster, render  # noqa: E402
from vinci_core.load import load, norm_url, parse_number  # noqa: E402
from vinci_core.text import classify_intent, core_tokens, tokens  # noqa: E402


class Parsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_number("1,300"), (1300.0, False))
        self.assertEqual(parse_number("1.3K"), (1300.0, False))
        self.assertEqual(parse_number("1K – 10K"), (1000.0, True))
        self.assertEqual(parse_number("4.2%"), (4.2, False))
        self.assertEqual(parse_number("n/a"), (None, False))

    def test_url_join_key(self):
        self.assertEqual(norm_url("https://www.Site.com/Page/#top"), norm_url("http://site.com/page"))

    def test_tokens_fold_plurals_and_drop_filler(self):
        self.assertEqual(tokens("how to make croissants"), frozenset({"croissant"}))
        self.assertEqual(core_tokens("best bakery near me"), frozenset({"bakery"}))

    def test_intent(self):
        self.assertEqual(classify_intent("x", "Commercial, Informational", []), ("commercial", "export"))
        self.assertEqual(classify_intent("acme login", None, ["acme"])[0], "navigational")
        self.assertEqual(classify_intent("bakery near me", None, [])[0], "local")
        self.assertEqual(classify_intent("sourdough", None, [])[0], "unclassified")


class Loading(unittest.TestCase):
    def test_sample_files_are_recognized(self):
        loaded = load([SAMPLE])
        kinds = {f["file"]: f["read_as"] for f in loaded.files}
        self.assertEqual(kinds["keyword_research.csv"], "keyword list")
        self.assertEqual(kinds["crawl_internal_html.csv"], "site crawl")
        self.assertEqual(kinds["gsc_pages.csv"], "Search Console pages")
        self.assertEqual(len(loaded.pages), 21)  # redirect, noindex and image left out
        self.assertEqual(loaded.demand_type, "search volume")

    def test_messy_file_with_title_lines_and_totals(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "kp.csv"
            p.write_text("Keyword Stats 2026\n\nKeyword\tAvg. monthly searches\nrye bread\t1K – 10K\n"
                         "Total\t99\n", encoding="utf-16")
            loaded = load([p])
        self.assertEqual([k["keyword"] for k in loaded.keywords], ["rye bread"])
        self.assertEqual(loaded.keywords[0]["demand"], 1000.0)
        self.assertTrue(any("ranges" in n for n in loaded.notes))

    def test_unknown_file_is_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "notes.csv"
            p.write_text("colour,shape\nred,round\n")
            loaded = load([p])
        self.assertTrue(any("not recognized" in n for n in loaded.notes))


class Clustering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load([SAMPLE])
        cls.result = cluster.build(cls.loaded, ["northwind"])
        cls.by_kw = {c["primary_keyword"]: c for c in cls.result["clusters"]}

    def test_lead_keyword_has_highest_demand_and_totals_add_up(self):
        for c in self.result["clusters"]:
            demands = [k["demand"] for k in c["keywords"]]
            self.assertEqual(demands[0], max(demands))
            self.assertEqual(c["total_demand"], sum(demands))
        self.assertEqual(self.result["totals"]["total_demand"],
                         sum(c["total_demand"] for c in self.result["clusters"]))

    def test_related_keywords_group_and_unrelated_stay_apart(self):
        sourdough = {k["keyword"] for k in self.by_kw["sourdough bread recipe"]["keywords"]}
        self.assertIn("how to make sourdough bread", sourdough)
        self.assertNotIn("sourdough starter", sourdough)

    def test_duplicates_removed(self):
        self.assertEqual(self.result["totals"]["keywords"], 43)

    def test_topics_map_to_existing_pages(self):
        self.assertTrue(self.by_kw["sourdough bread recipe"]["existing_page"]["url"].endswith("/blog/sourdough-bread-recipe"))
        self.assertEqual(self.by_kw["can you freeze bread"]["action"], "new page")

    def test_merge(self):
        merged = cluster.build(load([SAMPLE]), [], merges=[("birthday cake near me", "order birthday cake online")])
        c = next(c for c in merged["clusters"] if c["primary_keyword"] == "birthday cake near me")
        self.assertIn("order birthday cake online", {k["keyword"] for k in c["keywords"]})


class Auditing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loaded = load([SAMPLE])
        cls.result = audit.build(loaded, cluster.build(loaded, []))
        cls.pages = {p["url"].split(".example")[1]: p for p in cls.result["pages"]}

    def test_planted_issues_are_found(self):
        self.assertIn("title_too_long", self.pages["/blog/sourdough-starter-guide"]["issues"])
        self.assertIn("title_duplicate", self.pages["/about"]["issues"])
        self.assertIn("description_missing", self.pages["/blog/gluten-free-bread"]["issues"])
        self.assertIn("description_duplicate", self.pages["/contact"]["issues"])
        self.assertIn("title_misses_target_keyword", self.pages["/blog/sourdough-bread-recipe"]["issues"])
        self.assertEqual(self.pages["/classes"]["issues"], [])

    def test_low_click_rate_uses_this_sites_own_pages(self):
        self.assertIn("low_click_rate", self.pages["/blog/sourdough-bread-recipe"]["issues"])
        self.assertNotIn("low_click_rate", self.pages["/blog/croissant-recipe"]["issues"])
        # Too few impressions to judge, however low the rate.
        self.assertNotIn("low_click_rate", self.pages["/gift-cards"]["issues"])

    def test_brand_suffix_and_priority_order(self):
        self.assertEqual(self.result["brand_suffix"]["text"], " | Northwind Bakery")
        self.assertTrue(self.result["rewrite_queue"][0].endswith("/blog/sourdough-bread-recipe"))


class Checking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clusters = json.loads((EXAMPLE / "clusters.json").read_text())
        cls.briefs = json.loads((EXAMPLE / "briefs.json").read_text())
        cls.audit = json.loads((EXAMPLE / "title_audit.json").read_text())
        cls.rewrites = json.loads((EXAMPLE / "rewrites.json").read_text())

    def test_example_passes(self):
        self.assertEqual(check.check_briefs(self.clusters, self.briefs)[0], [])
        self.assertEqual(check.check_rewrites(self.audit, self.rewrites)[0], [])

    def _brief_errors(self, **changes):
        briefs = copy.deepcopy(self.briefs)
        briefs["briefs"][0].update(changes)
        return " ".join(check.check_briefs(self.clusters, briefs)[0])

    def test_invented_number_is_blocked(self):
        self.assertIn("90,000", self._brief_errors(summary="This topic gets 90,000 searches."))

    def test_number_inside_a_keyword_is_allowed(self):
        clusters = copy.deepcopy(self.clusters)
        clusters["clusters"][1]["keywords"].append(
            {"keyword": "top 10 sourdough tips", "demand": 10, "difficulty": None, "intent": "informational",
             "intent_source": "word rule", "position": None, "url": None})
        briefs = copy.deepcopy(self.briefs)
        briefs["briefs"][0]["summary"] = 'People also search "top 10 sourdough tips".'
        self.assertEqual(check.check_briefs(clusters, briefs)[0], [])

    def test_keyword_from_another_topic_is_blocked(self):
        self.assertIn("not in this cluster", self._brief_errors(target_keywords=["croissant recipe"]))

    def test_link_outside_the_site_is_blocked(self):
        self.assertIn("not a page in the crawl", self._brief_errors(internal_links=["https://example.org/x"]))

    def test_long_title_is_blocked(self):
        self.assertIn("limit is 60", self._brief_errors(working_title="x" * 61))

    def _rewrite_errors(self, index, **changes):
        rewrites = copy.deepcopy(self.rewrites)
        rewrites["rewrites"][index].update(changes)
        return " ".join(check.check_rewrites(self.audit, rewrites)[0])

    def test_rewrite_rules(self):
        self.assertIn("limit is 60", self._rewrite_errors(0, new_title="Sourdough Bread Recipe " + "x" * 50))
        self.assertIn("target keyword", self._rewrite_errors(0, new_title="A Lovely Loaf for Everyone | Northwind Bakery"))
        self.assertIn("already used", self._rewrite_errors(6, new_title="Bread Baking Classes | Northwind Bakery"))
        self.assertIn("reason", self._rewrite_errors(1, reason=""))
        self.assertEqual(self._rewrite_errors(0, new_title="A Lovely Loaf for Everyone | Northwind Bakery",
                                              keyword_waived="Client wants the product name first."), "")


class Rendering(unittest.TestCase):
    def test_outputs_are_written(self):
        clusters = json.loads((EXAMPLE / "clusters.json").read_text())
        briefs = json.loads((EXAMPLE / "briefs.json").read_text())
        result = json.loads((EXAMPLE / "title_audit.json").read_text())
        rewrites = json.loads((EXAMPLE / "rewrites.json").read_text())
        with tempfile.TemporaryDirectory() as d:
            paths = render.render_briefs(clusters, briefs, Path(d))
            html = paths[0].read_text(encoding="utf-8")
            self.assertIn("Sourdough Bread Recipe for Beginners", html)
            self.assertEqual(len(paths), 1 + len(briefs["briefs"]))
            sheet = render.render_rewrites(result, rewrites, Path(d))[0].read_text(encoding="utf-8-sig")
            self.assertEqual(len(sheet.strip().splitlines()), 1 + len(rewrites["rewrites"]))

    def test_cli_refuses_to_render_bad_work(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("clusters.json",):
                (Path(d) / name).write_text((EXAMPLE / name).read_text())
            briefs = json.loads((EXAMPLE / "briefs.json").read_text())
            briefs["briefs"][0]["summary"] = "Traffic will grow 300 percent."
            (Path(d) / "briefs.json").write_text(json.dumps(briefs))
            run = subprocess.run([sys.executable, str(SCRIPTS / "vinci.py"), "render-briefs", "--out", d],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertFalse((Path(d) / "briefs.html").exists())


if __name__ == "__main__":
    unittest.main()
