#!/usr/bin/env python3
"""PRANA Scent -> Google Merchant Center RSS 2.0 feed.

Reads public Shopify Ajax endpoints without Admin API keys.
A failed fetch or validation stops generation rather than publishing an incomplete feed.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

STORE = "https://pranascent.pl"
HANDLES = (
    "arabian-tea-opium",
    "botanic-salt-smoke",
    "leather-resin-core",
    "dark-bazaar",
    "meditation-woods",
    "zen-ritual",
    "fig-tea-opium",
)
GOOGLE_NS = "http://base.google.com/ns/1.0"
ET.register_namespace("g", GOOGLE_NS)
USER_AGENT = "PRANA-Merchant-Feed/1.0 (public Shopify product data)"


class StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value: str) -> str:
    parser = StripHTML()
    parser.feed(str(value or ""))
    return " ".join(html.unescape(" ".join(parser.parts)).split())


def secure_image_url(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("src") or value.get("url")
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("/"):
        value = STORE + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return value


def fetch_json(url: str, attempts: int = 3) -> dict:
    if not url.startswith(STORE + "/"):
        raise ValueError("Refusing non-store URL")
    for attempt in range(attempts):
        try:
            req = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "pl-PL,pl;q=0.9",
                    "User-Agent": USER_AGENT,
                },
            )
            with urlopen(req, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            return data
        except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Shopify read failed: {url}: {exc}") from exc
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def put(parent: ET.Element, key: str, value: str) -> None:
    ET.SubElement(parent, "{" + GOOGLE_NS + "}" + key).text = str(value)


def check_price(price, handle: str) -> int:
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0 or price > 2_000_000:
        raise ValueError(f"Invalid price in minor units: {handle}: {price!r}")
    return price


def as_feed(products: list[dict]) -> tuple[bytes, int]:
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "PRANA Scent – świece zapachowe"
    ET.SubElement(channel, "link").text = STORE
    ET.SubElement(channel, "description").text = "Aktualne produkty i warianty PRANA Scent"
    count = 0
    ids = set()
    for product in products:
        handle = str(product.get("handle", ""))
        if handle not in HANDLES:
            raise ValueError(f"Unexpected product handle: {handle}")
        title = plain(product.get("title", ""))
        description = plain(product.get("description", ""))[:4900]
        product_id = str(product.get("id", ""))
        variants = product.get("variants")
        if not product_id.isdigit() or not title or not description or not isinstance(variants, list) or not variants:
            raise ValueError(f"Missing product data or variants: {handle}")
        for variant in variants:
            variant_id = str(variant.get("id", ""))
            if not variant_id.isdigit() or variant_id in ids:
                raise ValueError(f"Missing/duplicate variant ID: {handle}")
            ids.add(variant_id)
            price_minor = check_price(variant.get("price"), handle)
            size = str(variant.get("option1") or "").strip()
            color = str(variant.get("option2") or "").strip()
            if not re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:g|kg)", size, flags=re.I) or not color:
                raise ValueError(f"Unexpected size/color: {handle} {variant_id}: {size}/{color}")
            if not isinstance(variant.get("available"), bool):
                raise ValueError(f"No availability flag: {handle}/{variant_id}")
            image = secure_image_url(variant.get("featured_image")) or secure_image_url(product.get("featured_image"))
            if not image:
                raise ValueError(f"Missing image: {handle}/{variant_id}")
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = f"Świeca zapachowa PRANA Scent {title} – {size}, {color}"
            ET.SubElement(item, "link").text = f"{STORE}/products/{handle}?variant={variant_id}"
            ET.SubElement(item, "description").text = description
            put(item, "id", variant_id)
            put(item, "item_group_id", product_id)
            put(item, "brand", "PRANA Scent")
            put(item, "condition", "new")
            put(item, "price", f"{price_minor / 100:.2f} PLN")
            put(item, "availability", "in_stock" if variant["available"] else "out_of_stock")
            put(item, "image_link", image)
            put(item, "size", size.replace("g", " g"))
            put(item, "color", color)
            put(item, "product_type", "Dom i ogród > Zapachy do domu > Świece zapachowe")
            put(item, "custom_label_0", size)
            sku = str(variant.get("sku") or "").strip()
            if sku:
                put(item, "mpn", sku)
            count += 1
    if len(products) != len(HANDLES) or count < len(HANDLES):
        raise ValueError(f"Incomplete catalogue: {len(products)} products, {count} variants")
    ET.indent(root, space="  ")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    ET.fromstring(payload)
    return payload, count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("merchant-feed.xml"))
    parser.add_argument("--test-fixtures", type=Path, help="Offline test: JSON file with 7 product objects")
    args = parser.parse_args()
    if args.test_fixtures:
        products = json.loads(args.test_fixtures.read_text(encoding="utf-8"))
    else:
        cart = fetch_json(f"{STORE}/cart.js")
        if cart.get("currency") != "PLN":
            raise ValueError(f"Unexpected storefront currency: {cart.get('currency')!r}")
        products = [fetch_json(f"{STORE}/products/{handle}.js") for handle in HANDLES]
    feed, count = as_feed(products)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".tmp")
    tmp.write_bytes(feed)
    tmp.replace(args.output)
    print(f"OK: {count} variants -> {args.output} ({len(feed)} bytes)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
