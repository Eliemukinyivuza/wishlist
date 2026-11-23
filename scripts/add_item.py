#!/usr/bin/env python3
"""Add a product to items.json from a link sent by the phone button.

The phone Shortcut opens an issue titled "Add to wishlist" whose body looks like:

    url: https://www.example.com/some-product
    target: 60
    for: Me

Only the url line is required. This script reads the product page for its
name, photo, shop, size and price, adds the item, and prints a one-line
summary to ADDED_PATH for the reply on the issue.
"""
import datetime
import json
import os
import re
import sys
import unicodedata
from html import unescape
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from check_prices import fetch, jsonld_products, meta, read_price, to_price  # noqa: E402

ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
ADDED_PATH = os.environ.get("ADDED_PATH", "added.txt")

PERFUME = re.compile(r"parfum|toilette|cologne|fragrance|perfume|\bedp\b|\bedt\b|elixir", re.I)
BAG = re.compile(r"\bbag\b|duffle|duffel|tote|backpack|handbag|purse|clutch|crossbody", re.I)
SKIN = re.compile(r"serum|moisturi[sz]er|cleanser|spf|sunscreen|toner|cream\b", re.I)
HAIR = re.compile(r"shampoo|conditioner|hair\s?oil|curl|edge control|leave-in", re.I)
SHOES = re.compile(r"trainer|sneaker|boot\b|boots\b|heel|sandal|loafer", re.I)


def parse_body(body):
    fields = {}
    for line in (body or "").splitlines():
        m = re.match(r"\s*(url|link|target|for|category|priority)\s*[:=]\s*(.*)$", line, re.I)
        if m:
            fields[m.group(1).lower()] = m.group(2).strip()
    if "url" not in fields and "link" in fields:
        fields["url"] = fields["link"]
    # Shop apps often share "Product name https://link", so keep just the link.
    m = re.search(r"https?://\S+", fields.get("url", "")) or re.search(r"https?://\S+", body or "")
    if m:
        fields["url"] = m.group(0)
    return fields


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "item"


def clean_name(name, shop):
    name = unescape(name or "").strip()
    # Drop " | Shop name" or " - Shop name" tails that page titles carry.
    parts = re.split(r"\s+[|–—-]\s+", name)
    if len(parts) > 1 and shop and any(shop.lower() in p.lower() for p in parts[1:]):
        name = parts[0]
    return re.sub(r"\s+", " ", name).strip()


def guess_category(text):
    for label, rx in (("Perfume", PERFUME), ("Bag", BAG), ("Skincare", SKIN), ("Hair", HAIR), ("Shoes", SHOES)):
        if rx.search(text):
            return label
    return "Other"


def main():
    fields = parse_body(os.environ.get("ISSUE_BODY", ""))
    url = fields.get("url", "").rstrip(").,")
    if not url.startswith("http"):
        write_added("I could not find a link in that message, so nothing was added.")
        return

    with open(ITEMS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    def same(a, b):
        pa, pb = urlparse(a), urlparse(b)
        return pa.netloc.replace("www.", "") == pb.netloc.replace("www.", "") and pa.path.rstrip("/") == pb.path.rstrip("/")

    for it in data["items"]:
        if it.get("url") and same(it["url"], url):
            write_added(f"{it['name']} is already on your wishlist.")
            return

    try:
        html = fetch(url)
    except Exception as e:  # blocked, missing page or network trouble
        html = ""
        print(f"Could not load the page: {e}")

    products = jsonld_products(html) if html else []
    shop = meta(html, "og:site_name") if html else None
    if not shop:
        shop = urlparse(url).netloc.replace("www.", "").split(".")[0].replace("-", " ").title()

    name = None
    brand = None
    for p in products:
        if p.get("name"):
            name = str(p["name"])
            b = p.get("brand")
            brand = b.get("name") if isinstance(b, dict) else b
            break
    if not name and html:
        name = meta(html, "og:title", "twitter:title")
    if not name and html:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        name = m.group(1) if m else None
    name = clean_name(name or urlparse(url).path.strip("/").split("/")[-1].replace("-", " ").title(), shop)
    if brand and isinstance(brand, str) and not name.lower().startswith(brand.lower()):
        name = f"{brand} {name}"

    size_m = re.search(r"(\d+(?:\.\d+)?)\s?(ml|l|g|oz)\b", name + " " + url, re.I)
    size = (size_m.group(1) + size_m.group(2).lower()) if size_m else ""
    # Keep the card title tidy: the size shows next to the shop instead.
    if size_m:
        name = re.sub(r"\s*[-,]?\s*" + re.escape(size_m.group(0)) + r"\b", "", name, flags=re.I).strip(" -,")

    target = to_price(re.sub(r"[£\s]", "", fields.get("target", "")))
    who = fields.get("for", "").strip() or "Me"
    ids = {it.get("id") for it in data["items"]}
    base = slug(name)
    item_id, n = base, 2
    while item_id in ids:
        item_id, n = f"{base}-{n}", n + 1

    item = {
        "id": item_id,
        "name": name,
        "category": fields.get("category") or guess_category(name + " " + url),
        "for": who.capitalize() if who.lower() == "me" else who,
        "priority": fields.get("priority") or "Want",
        "url": url,
        "retailer": shop,
        "size": size,
        "target": target,
        "notes": "",
        "added": datetime.date.today().isoformat(),
    }

    if html:
        image = meta(html, "og:image", "og:image:secure_url", "twitter:image")
        if image:
            item["image"] = urljoin(url, image)
        found = read_price(html, url, size)
        if found and (not found.get("currency") or found["currency"].upper() == "GBP"):
            today = datetime.date.today().isoformat()
            item.update(
                price=found["price"],
                inStock=found["in_stock"],
                lowest=found["price"],
                lastChecked=today,
                checkStatus="OK",
                history=[{"date": today, "price": found["price"]}],
            )
        else:
            item["checkStatus"] = "Photo found but no price on the page" if "image" in item else "No price on the page"
    else:
        item["checkStatus"] = "Shop blocked the robot"

    data["items"].append(item)
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    price = f" at £{item['price']:.2f}" if "price" in item else ""
    extra = "" if "price" in item else f" I could not read the price yet ({item['checkStatus'].lower()})."
    write_added(f"Added {item['name']}{price} from {shop} 🎀{extra}")


def write_added(text):
    print(text)
    with open(ADDED_PATH, "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
