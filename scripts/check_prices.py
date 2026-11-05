#!/usr/bin/env python3
"""Read the current price and photo from every product link in items.json.

Runs daily in GitHub Actions. Uses only the Python standard library.
Each page is read for schema.org JSON-LD (the price shops publish for Google)
and for og:image (the photo shown when a link is shared).
"""
import datetime
import json
import os
import re
import time
import urllib.error
import urllib.request
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
ALERTS_PATH = os.environ.get("ALERTS_PATH", "alerts.txt")
PAUSE_SECONDS = float(os.environ.get("PAUSE_SECONDS", "3"))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read(3_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def meta(html, *names):
    """Value of the first <meta> tag whose property, name or itemprop matches."""
    for m in re.finditer(r"<meta\b[^>]*>", html, re.I):
        tag = m.group(0)
        key = re.search(r'(?:property|name|itemprop)\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        val = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        if key and val and key.group(1).lower() in names:
            return unescape(val.group(1)).strip()
    return None


def jsonld_products(html):
    found = []
    pattern = r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    for m in re.finditer(pattern, html, re.I | re.S):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                t = d.get("@type")
                types = t if isinstance(t, list) else [t]
                if "Product" in types or "ProductGroup" in types:
                    found.append(d)
                for key in ("@graph", "hasVariant", "mainEntity"):
                    if key in d:
                        stack.append(d[key])
    return found


def to_price(value):
    try:
        return round(float(str(value).replace(",", "")), 2)
    except (TypeError, ValueError):
        return None


def offers_of(product):
    offers = product.get("offers")
    if isinstance(offers, dict):
        if "offers" in offers:
            return offers_of({"offers": offers["offers"]}) or [offers]
        return [offers]
    if isinstance(offers, list):
        out = []
        for o in offers:
            if isinstance(o, dict):
                out.extend(offers_of({"offers": o}))
        return out
    return []


def read_price(html, url):
    """Return {'price', 'currency', 'in_stock'} or None."""
    variant = (parse_qs(urlparse(url).query).get("variant") or [None])[0]
    candidates = []
    for product in jsonld_products(html):
        for offer in offers_of(product):
            price = to_price(offer.get("price"))
            if price is None:
                price = to_price(offer.get("lowPrice"))
            if price is None and isinstance(offer.get("priceSpecification"), dict):
                price = to_price(offer["priceSpecification"].get("price"))
            if price is None:
                continue
            candidates.append(
                {
                    "price": price,
                    "currency": offer.get("priceCurrency"),
                    "url": str(offer.get("url", "")),
                    "in_stock": "OutOfStock" not in str(offer.get("availability", "")),
                }
            )
    if candidates:
        if variant:
            matched = [c for c in candidates if variant in c["url"]]
            if matched:
                candidates = matched
        in_stock = [c for c in candidates if c["in_stock"]]
        return (in_stock or candidates)[0]
    price = to_price(meta(html, "product:price:amount", "og:price:amount", "price"))
    if price is not None:
        currency = meta(html, "product:price:currency", "og:price:currency", "pricecurrency")
        return {"price": price, "currency": currency, "in_stock": True}
    return None


def main():
    with open(ITEMS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    today = datetime.date.today().isoformat()
    alerts = []

    for index, item in enumerate(data["items"]):
        name = item.get("name", item.get("id", "item"))
        url = item.get("url")
        if not url:
            item["checkStatus"] = "No link yet"
            print(f"- {name}: no link")
            continue
        if index:
            time.sleep(PAUSE_SECONDS)
        try:
            html = fetch(url)
        except urllib.error.HTTPError as e:
            item["checkStatus"] = f"Shop blocked or removed the page (HTTP {e.code})"
            print(f"- {name}: HTTP {e.code}")
            continue
        except Exception as e:  # network trouble, bad certificate, timeout
            item["checkStatus"] = f"Could not load the page ({type(e).__name__})"
            print(f"- {name}: {type(e).__name__}")
            continue

        image = meta(html, "og:image", "og:image:secure_url", "twitter:image")
        if image:
            item["image"] = urljoin(url, image)

        found = read_price(html, url)
        if not found:
            item["checkStatus"] = "Photo found but no price on the page"
            print(f"- {name}: no price found")
            continue
        if found["currency"] and found["currency"].upper() != "GBP":
            item["checkStatus"] = f"Price is in {found['currency']}, not pounds"
            print(f"- {name}: currency {found['currency']}")
            continue

        price = found["price"]
        history = item.setdefault("history", [])
        prior = [h["price"] for h in history if h["date"] != today]
        previous = prior[-1] if prior else None

        if history and history[-1]["date"] == today:
            history[-1]["price"] = price
        else:
            history.append({"date": today, "price": price})
        del history[:-365]

        item["price"] = price
        item["inStock"] = found["in_stock"]
        item["lowest"] = min(h["price"] for h in history)
        item["lastChecked"] = today
        item["checkStatus"] = "OK"

        target = item.get("target")
        if target is not None and price <= target and not (previous is not None and previous <= target):
            alerts.append(f"{name} is now £{price:.2f}, at or under your £{target:.2f} target")
        elif prior and price < min(prior):
            alerts.append(f"{name} hit a new lowest price: £{price:.2f}")
        print(f"- {name}: £{price:.2f}")

    data["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(alerts) + ("\n" if alerts else ""))
    print(f"{len(alerts)} alert(s)")


if __name__ == "__main__":
    main()
