#!/usr/bin/env python3
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from email.utils import format_datetime
import html
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

import feedparser
import requests

SOURCE_FEED = "https://www.zendalibros.com/tag/patente-de-corso/feed"
SITE_URL = "https://www.zendalibros.com/tag/patente-de-corso/"
WP_BASE = "https://www.zendalibros.com/wp-json/wp/v2"

OUTPUT = Path("docs/feed.xml")
MAX_PAGES = 100
REQUEST_TIMEOUT = 30
PAUSE_BETWEEN_REQUESTS = 0.20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PatenteDeCorsoArchiveFeed/1.1; "
        "+https://github.com/)"
    )
}


def clean_title(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(value).strip() or "Sin título"


def wp_date_to_rfc2822(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return format_datetime(dt.astimezone(timezone.utc))
    except ValueError:
        return None


def fetch_via_rest(session: requests.Session):
    print("Intentando recuperar el archivo mediante la API REST de WordPress…")

    tag_response = session.get(
        f"{WP_BASE}/tags",
        params={"slug": "patente-de-corso", "per_page": 100},
        timeout=REQUEST_TIMEOUT,
    )
    tag_response.raise_for_status()
    tags = tag_response.json()

    if not tags:
        raise RuntimeError("La API REST no devolvió la etiqueta patente-de-corso.")

    tag_id = tags[0]["id"]
    print(f"Etiqueta localizada. ID de WordPress: {tag_id}")

    entries = []
    page = 1
    total_pages = None

    while page <= MAX_PAGES:
        response = session.get(
            f"{WP_BASE}/posts",
            params={
                "tags": tag_id,
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "desc",
                "_fields": "id,date_gmt,link,title,excerpt",
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code in (400, 404) and page > 1:
            break

        response.raise_for_status()
        posts = response.json()

        if total_pages is None:
            total_pages = int(response.headers.get("X-WP-TotalPages", "0") or 0)
            total_items = response.headers.get("X-WP-Total")
            if total_items:
                print(f"WordPress informa de {total_items} artículos en total.")
            if total_pages:
                print(f"Páginas REST necesarias: {total_pages}")

        if not posts:
            break

        for post in posts:
            entries.append(
                {
                    "id": f"zendalibros-post-{post['id']}",
                    "title": clean_title(post.get("title", {}).get("rendered", "")),
                    "link": post.get("link"),
                    "published": wp_date_to_rfc2822(post.get("date_gmt")),
                    "summary": post.get("excerpt", {}).get("rendered", ""),
                    "sort_ts": (
                        datetime.fromisoformat(post["date_gmt"])
                        .replace(tzinfo=timezone.utc)
                        .timestamp()
                        if post.get("date_gmt")
                        else 0
                    ),
                }
            )

        print(f"  REST página {page}: {len(posts)} artículos; total: {len(entries)}")

        if total_pages and page >= total_pages:
            break
        if len(posts) < 100 and not total_pages:
            break

        page += 1
        time.sleep(PAUSE_BETWEEN_REQUESTS)

    if not entries:
        raise RuntimeError("La API REST no devolvió artículos.")

    return entries


def feed_page_url(page: int) -> str:
    base = SOURCE_FEED.rstrip("/") + "/"
    return base if page == 1 else f"{base}?paged={page}"


def fetch_via_paginated_feed(session: requests.Session):
    print("Usando como alternativa el RSS paginado de WordPress…")

    seen = set()
    entries = []

    for page in range(1, MAX_PAGES + 1):
        url = feed_page_url(page)
        response = session.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code in (404, 410):
            break

        response.raise_for_status()
        parsed = feedparser.parse(response.content)

        if not parsed.entries:
            break

        new_on_page = 0

        for entry in parsed.entries:
            key = (
                entry.get("id")
                or entry.get("guid")
                or entry.get("link")
                or f'{entry.get("title", "")}|{entry.get("published", "")}'
            )

            if key in seen:
                continue

            seen.add(key)
            new_on_page += 1

            parsed_date = entry.get("published_parsed") or entry.get("updated_parsed")
            sort_ts = calendar.timegm(parsed_date) if parsed_date else 0

            entries.append(
                {
                    "id": key,
                    "title": entry.get("title", "Sin título"),
                    "link": entry.get("link"),
                    "published": entry.get("published") or entry.get("updated"),
                    "summary": entry.get("summary", ""),
                    "sort_ts": sort_ts,
                }
            )

        print(
            f"  RSS página {page}: {len(parsed.entries)} recibidos, "
            f"{new_on_page} nuevos; total: {len(entries)}"
        )

        # Evita bucles si el servidor ignora ?paged=N y repite la página 1.
        if page > 1 and new_on_page == 0:
            break

        time.sleep(PAUSE_BETWEEN_REQUESTS)

    if not entries:
        raise RuntimeError("El RSS paginado tampoco devolvió artículos.")

    return entries


def fetch_all_entries():
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        entries = fetch_via_rest(session)
        print("Método usado: API REST.")
    except Exception as exc:
        print(f"La API REST no pudo usarse: {exc}")
        entries = fetch_via_paginated_feed(session)
        print("Método usado: RSS paginado.")

    # Deduplicación final por enlace/ID.
    deduped = {}
    for entry in entries:
        key = entry.get("link") or entry.get("id")
        if key:
            deduped[key] = entry

    result = list(deduped.values())
    result.sort(key=lambda e: e.get("sort_ts", 0), reverse=True)
    return result


def add_text(parent, tag, text):
    if text is None:
        return None
    node = ET.SubElement(parent, tag)
    node.text = str(text)
    return node


def build_rss(entries):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    add_text(channel, "title", "Patente de corso — archivo completo (Zenda)")
    add_text(channel, "link", SITE_URL)
    add_text(
        channel,
        "description",
        "Feed no oficial que reúne el archivo completo de la etiqueta "
        "Patente de corso publicada en Zenda. Todos los artículos enlazan a Zenda."
    )
    add_text(channel, "language", "es")
    add_text(channel, "generator", "PatenteDeCorsoArchiveFeed")

    for entry in entries:
        item = ET.SubElement(channel, "item")

        add_text(item, "title", entry.get("title", "Sin título"))
        link = entry.get("link") or SITE_URL
        add_text(item, "link", link)

        guid_value = entry.get("id") or link
        guid = add_text(item, "guid", guid_value)
        if guid is not None:
            guid.set("isPermaLink", "false")

        if entry.get("published"):
            add_text(item, "pubDate", entry["published"])

        if entry.get("summary"):
            add_text(item, "description", entry["summary"])

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)


def main():
    entries = fetch_all_entries()

    if not entries:
        raise SystemExit("No se recuperó ningún artículo; no se sobrescribe el feed.")

    build_rss(entries)
    print(f"\nFeed generado: {OUTPUT}")
    print(f"Artículos totales: {len(entries)}")


if __name__ == "__main__":
    main()
