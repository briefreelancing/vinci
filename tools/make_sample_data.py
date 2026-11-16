"""Write the synthetic sample exports for the fictional client Northwind Bakery.

Everything here is invented. The files copy the column layouts of a keyword
research export, a Screaming Frog crawl and a Search Console pages export so
Vinci can be tried without real client data.

    python tools/make_sample_data.py
"""

from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "sample-data" / "northwind-bakery"
SITE = "https://www.northwindbakery.example"
B = " | Northwind Bakery"

# keyword, intent, monthly searches, difficulty, CPC
KEYWORDS = [
    ("sourdough bread recipe", "Informational", 40500, 62, 0.42),
    ("easy sourdough bread recipe", "Informational", 8100, 48, 0.38),
    ("sourdough bread recipe for beginners", "Informational", 5400, 41, 0.35),
    ("how to make sourdough bread", "Informational", 12100, 58, 0.40),
    ("best sourdough bread recipe", "Commercial", 2400, 50, 0.33),
    ("sourdough starter", "Informational", 33100, 55, 0.51),
    ("how to make sourdough starter", "Informational", 14800, 47, 0.44),
    ("sourdough starter recipe", "Informational", 9900, 45, 0.41),
    ("how to feed sourdough starter", "Informational", 3600, 30, 0.22),
    ("sourdough starter from scratch", "Informational", 1900, 33, 0.25),
    ("gluten free bread", "Commercial", 18100, 52, 1.10),
    ("gluten free bread recipe", "Informational", 12100, 44, 0.48),
    ("best gluten free bread", "Commercial", 4400, 40, 0.95),
    ("gluten free bread near me", "", 1600, 28, 1.30),
    ("birthday cake near me", "", 8100, 39, 1.85),
    ("birthday cake delivery", "Transactional", 6600, 38, 2.40),
    ("custom birthday cakes", "Commercial", 4400, 36, 2.10),
    ("order birthday cake online", "Transactional", 2900, 35, 2.65),
    ("wedding cake prices", "Commercial", 5400, 33, 1.75),
    ("wedding cake cost", "Commercial", 3600, 31, 1.60),
    ("how much does a wedding cake cost", "Informational", 2400, 29, 1.20),
    ("croissant recipe", "Informational", 14800, 54, 0.30),
    ("how to make croissants", "Informational", 9900, 50, 0.28),
    ("chocolate croissant recipe", "Informational", 3600, 44, 0.26),
    ("easy croissant recipe", "Informational", 2900, 42, 0.24),
    ("bakery near me", "", 135000, 71, 1.05),
    ("best bakery near me", "", 9900, 60, 1.15),
    ("bakery open now", "", 6600, 55, 0.90),
    ("bread baking class", "Transactional", 2900, 27, 3.10),
    ("bread making classes near me", "", 1900, 24, 3.40),
    ("baking classes for beginners", "Commercial", 1600, 26, 2.90),
    ("sourdough class", "Transactional", 1300, 22, 3.25),
    ("cinnamon roll recipe", "Informational", 49500, 60, 0.36),
    ("overnight cinnamon rolls", "Informational", 6600, 40, 0.31),
    ("best cinnamon rolls", "Commercial", 5400, 48, 0.55),
    ("cinnamon rolls near me", "", 4400, 35, 0.98),
    ("northwind bakery", "Navigational", 1900, 12, 0.60),
    ("northwind bakery menu", "Navigational", 720, 10, 0.45),
    ("northwind bakery hours", "Navigational", 480, 9, 0.40),
    ("how to store bread", "Informational", 6600, 30, 0.18),
    ("how to store sourdough bread", "Informational", 4400, 25, 0.16),
    ("can you freeze bread", "Informational", 5400, 22, 0.12),
    ("how long does bread last", "Informational", 3600, 20, 0.10),
    ("Sourdough Bread Recipe", "Informational", 40500, 62, 0.42),  # duplicate on purpose
]

D_OK = "Fresh bread, pastries and cakes baked every morning in our ovens. See what is coming out today and order ahead."
D_VISIT = "Find your nearest Northwind Bakery, with opening hours, parking and directions for all three of our shops."

# path, title, meta description, H1, status, indexability, content type
PAGES = [
    ("/", "Northwind Bakery", D_OK, "Baked fresh every morning", 200, "Indexable", "text/html; charset=utf-8"),
    ("/about", "Northwind Bakery", "Our story.", "About us", 200, "Indexable", "text/html; charset=utf-8"),
    ("/menu", "Menu" + B, "Browse the full Northwind Bakery menu: breads, pastries, cakes, coffee and seasonal specials, with prices.", "Our menu", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog", "Blog" + B, "Recipes, baking tips and stories from the Northwind Bakery kitchen, written by the people who bake your bread.", "From the kitchen", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/sourdough-bread-recipe", "Sourdough" + B, "Our head baker shares the loaf we sell out of every day, with timings, photos of each stage and fixes for common problems.", "Our Sourdough Bread Recipe", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/sourdough-starter-guide", "How to Make a Sourdough Starter From Scratch: The Complete Step-by-Step Guide for Beginners" + B, "A day-by-day guide to growing a lively sourdough starter from flour and water, including what to do when it stalls.", "How to Make a Sourdough Starter", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/gluten-free-bread", "Gluten Free Bread Recipe That Rises" + B, "", "Gluten Free Bread Recipe", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/croissant-recipe", "Croissant Recipe: Buttery Layers at Home" + B, "Laminated dough without the fear. Our croissant recipe breaks the folds into simple steps you can spread over two days.", "Croissant Recipe", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/cinnamon-rolls", "Blog" + B, "Soft, sticky cinnamon rolls you shape the night before and bake in the morning. Includes the cream cheese glaze we use in the shop.", "Overnight Cinnamon Roll Recipe", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/how-to-store-bread", "How to Store Bread So It Stays Fresh" + B, "Counter, bread box, fridge or freezer? How to store each kind of bread so the crust and crumb last as long as possible.", "How to Store Bread", 200, "Indexable", "text/html; charset=utf-8"),
    ("/blog/baking-tips", "12 Baking Tips From Our Bakers" + B, "Small habits that make a big difference at home, from weighing flour to reading your oven, shared by the Northwind team.", "Baking tips", 200, "Indexable", "text/html; charset=utf-8"),
    ("/cakes/birthday", "Birthday Cakes" + B, "Cakes for birthdays.", "Birthday Cakes", 200, "Indexable", "text/html; charset=utf-8"),
    ("/cakes/wedding", "Wedding Cakes and Prices" + B, "See our wedding cake styles, flavors and starting prices, then book a free tasting with our cake designer.", "Wedding Cakes", 200, "Indexable", "text/html; charset=utf-8"),
    ("/classes", "Bread Baking Classes" + B, "Hands-on bread baking classes for beginners and keen home bakers, held on weekends in our production kitchen.", "Bread Baking Classes", 200, "Indexable", "text/html; charset=utf-8"),
    ("/bread", "Our Breads: Sourdough, Rye, Baguettes" + B, "Sourdough, seeded rye, baguettes and soft sandwich loaves, baked from scratch each morning with long, slow fermentation.", "Our breads", 200, "Indexable", "text/html; charset=utf-8"),
    ("/pastries", "Pastries and Viennoiserie" + B, "Croissants, pain au chocolat, danishes and seasonal fruit tarts, laminated by hand and baked in small batches all day.", "Pastries", 200, "Indexable", "text/html; charset=utf-8"),
    ("/catering", "Bakery Catering for Offices and Events" + B, "Breakfast platters, sandwich boxes and dessert tables for meetings and celebrations, delivered across the city.", "Catering", 200, "Indexable", "text/html; charset=utf-8"),
    ("/order", "Order Online for Pickup" + B, "Order bread, pastries and cakes online and collect from your nearest Northwind Bakery at a time that suits you.", "Order online", 200, "Indexable", "text/html; charset=utf-8"),
    ("/locations", "Our Locations and Opening Hours" + B, D_VISIT, "Find us", 200, "Indexable", "text/html; charset=utf-8"),
    ("/contact", "Contact Us" + B, D_VISIT, "Get in touch", 200, "Indexable", "text/html; charset=utf-8"),
    ("/gift-cards", "Bakery Gift Cards" + B, "Give the gift of fresh bread. Northwind Bakery gift cards can be used in any of our shops or for online orders.", "Gift cards", 200, "Indexable", "text/html; charset=utf-8"),
    ("/old-menu", "", "", "", 301, "Non-Indexable", "text/html; charset=utf-8"),
    ("/cart", "Your Cart" + B, "", "Cart", 200, "Non-Indexable", "text/html; charset=utf-8"),
    ("/images/logo.png", "", "", "", 200, "Indexable", "image/png"),
]

# path, impressions, click rate %, average position
GSC = [
    ("/", 9800, 31.0, 1.2), ("/menu", 4100, 18.5, 2.1), ("/about", 900, 9.0, 2.8),
    ("/locations", 3300, 14.2, 2.5), ("/contact", 1200, 8.1, 3.0),
    ("/blog/sourdough-bread-recipe", 42000, 1.1, 5.2), ("/blog/sourdough-starter-guide", 21500, 5.1, 4.8),
    ("/blog/croissant-recipe", 11800, 4.2, 5.5), ("/blog/how-to-store-bread", 7400, 6.0, 4.1),
    ("/blog/gluten-free-bread", 9600, 3.9, 6.0), ("/blog/cinnamon-rolls", 15200, 4.4, 5.9),
    ("/classes", 2600, 5.5, 4.4),
    ("/cakes/birthday", 8700, 0.5, 8.2), ("/cakes/wedding", 5200, 2.1, 7.5), ("/pastries", 3100, 1.6, 9.0),
    ("/bread", 4800, 1.9, 8.8), ("/catering", 1900, 2.4, 7.2), ("/order", 2200, 1.5, 9.5),
    ("/blog/baking-tips", 1400, 1.2, 14.3), ("/gift-cards", 60, 5.0, 11.0),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "keyword_research.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Keyword", "Intent", "Search Volume", "Keyword Difficulty", "CPC (USD)"])
        for kw, intent, vol, kd, cpc in KEYWORDS:
            w.writerow([kw, intent, f"{vol:,}", kd, f"{cpc:.2f}"])
    with (OUT / "crawl_internal_html.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Content Type", "Status Code", "Indexability", "Title 1", "Title 1 Length",
                    "Meta Description 1", "Meta Description 1 Length", "H1-1"])
        for path, title, desc, h1, status, index, ctype in PAGES:
            w.writerow([SITE + path, ctype, status, index, title, len(title), desc, len(desc), h1])
    with (OUT / "gsc_pages.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Top pages", "Clicks", "Impressions", "CTR", "Position"])
        for path, imps, ctr, pos in GSC:
            w.writerow([SITE + path, round(imps * ctr / 100), imps, f"{ctr}%", pos])
    print(f"wrote sample exports to {OUT}")


if __name__ == "__main__":
    main()
