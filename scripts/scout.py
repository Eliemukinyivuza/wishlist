#!/usr/bin/env python3
"""Deal scout: look for each wishlist item at other UK shops.

Runs weekly. Uses Google Shopping results through SerpApi, which needs a
free API key saved as the repository secret SERPAPI_KEY. Without the key the
scout does nothing.

It is strict on purpose: a result only counts if every word of the item's
name and its size appear in the result title, and it is not a gift set,
tester, sample, refill or miniature (unless the item itself is one).
"""
import datetime
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
ALERTS_PATH = os.environ.get("ALERTS_PATH", "alerts.txt")
KEY = os.environ.get("SERPAPI_KEY", "").strip()
MIN_SAVING = 1.00  # pounds

AVOID = ["gift set", "giftset", "set", "tester", "sample", "refill", "mini", "miniature", "travel", "vial",
         "body lotion", "shower gel", "deodorant", "hair mist", "bundle", "duo", "trio", "used", "pre-owned", "box"]
SKIP_WORDS = {"eau", "de", "la", "le", "the", "and", "&", "for", "with", "of", "parfum", "toilette", "edp", "edt",
              "spray", "women", "woman", "her", "ml", "paco"}
# Words that turn a perfume into a different version ("Lady Million Royal").
FLANKERS = {"royal", "intense", "intensa", "elixir", "absolu", "absolute", "prive", "privee", "gold", "fabulous",
            "empire", "lucky", "love", "blush", "extreme", "noir", "rouge", "sport", "nectar", "fever", "sparkle",
            "crystal", "bloom", "dream", "night", "aqua", "eclat", "nude", "flora", "sheer", "legere", "le parfum"}


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def words(text):
    return [w for w in norm(text).split() if w not in SKIP_WORDS]


def matches(item, title):
    t = " " + norm(title) + " "
    tight = t.replace(" ", "")
    for w in words(item["name"]):
        if f" {w} " not in t:
            return False
    size = norm(item.get("size", "")).replace(" ", "")
    if size and size not in tight:
        return False
    own = " " + norm(item["name"]) + " "
    for f in FLANKERS:
        if f" {f} " in t and f" {f} " not in own:
            return False
    for bad in AVOID:
        if f" {bad} " in t and f" {bad} " not in own:
            return False
    return True


def same_shop(a, b):
    return norm(a).replace(" ", "")[:8] == norm(b).replace(" ", "")[:8]


def search(query):
    params = urllib.parse.urlencode({
        "engine": "google_shopping", "q": query, "gl": "uk", "hl": "en",
        "location": "United Kingdom", "api_key": KEY,
    })
    with urllib.request.urlopen("https://serpapi.com/search.json?" + params, timeout=40) as r:
        return json.load(r)


def main():
    if not KEY:
        print("No SERPAPI_KEY secret yet, so the scout is resting.")
        open(ALERTS_PATH, "w").close()
        return

    with open(ITEMS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.date.today().isoformat()
    alerts = []

    for item in data["items"]:
        query = " ".join(x for x in (item["name"], item.get("size", "")) if x)
        try:
            res = search(query)
        except Exception as e:
            print(f"- {item['name']}: search failed ({type(e).__name__})")
            continue
        best = None
        for r in res.get("shopping_results", []):
            price = r.get("extracted_price")
            shop = r.get("source", "")
            if price is None or not str(r.get("price", "")).startswith("£"):
                continue
            if not matches(item, r.get("title", "")):
                continue
            if item.get("retailer") and same_shop(shop, item["retailer"]):
                continue
            if best is None or price < best["price"]:
                best = {
                    "price": round(float(price), 2),
                    "shop": shop,
                    "url": r.get("product_link") or r.get("link") or "",
                    "title": r.get("title", "")[:120],
                    "checked": today,
                }
        current = item.get("price")
        old = item.get("elsewhere")
        if best and (current is None or best["price"] <= current - MIN_SAVING):
            item["elsewhere"] = best
            if not old or best["price"] < old.get("price", 1e9) - 0.005:
                saving = f", £{current - best['price']:.2f} less than {item.get('retailer') or 'your shop'}" if current else ""
                alerts.append(f"{item['name']} is £{best['price']:.2f} at {best['shop']}{saving}")
            print(f"- {item['name']}: cheaper at {best['shop']} £{best['price']:.2f}")
        else:
            item.pop("elsewhere", None)
            print(f"- {item['name']}: nothing cheaper found")
        time.sleep(1)

    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(alerts) + ("\n" if alerts else ""))
    print(f"{len(alerts)} alert(s)")


if __name__ == "__main__":
    main()
