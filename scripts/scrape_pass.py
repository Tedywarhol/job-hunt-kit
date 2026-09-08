#!/usr/bin/env python3
"""Scrape les offres de https://www.pass.fonction-publique.gouv.fr/ selon les filtres spécifiés."""
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

from typing import Any, Dict, List, Set

ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL: str = "https://www.pass.fonction-publique.gouv.fr"
SEARCH_URL: str = f"{BASE_URL}/recherche-offre"

DOMAINS: List[int] = [1085, 1088, 1101, 1107]
PAYS: List[int] = [837]
REGION: List[int] = [856]


def get_search_page_url(page_num: int = 0, items_per_page: int = 48) -> str:
    params: List[str] = []
    for d in DOMAINS:
        params.append(f"field_domaine_d_activite_target_id%5B%5D={d}")
    for p in PAYS:
        params.append(f"field_pays_target_id%5B%5D={p}")
    for r in REGION:
        params.append(f"field_region_target_id%5B%5D={r}")
    params.append(f"items_per_page={items_per_page}")
    if page_num > 0:
        params.append(f"page={page_num}")
    return f"{SEARCH_URL}?{'&'.join(params)}"


def scrape_all_list_offers() -> List[Dict[str, Any]]:
    page_num = 0
    all_offers: List[Dict[str, Any]] = []
    seen_links: Set[str] = set()

    while True:
        url = get_search_page_url(page_num=page_num, items_per_page=48)
        print(f"Fetching page {page_num}: {url}...")
        res = Fetcher.get(url, stealthy_headers=True, timeout=30)
        if res.status != 200:
            print(f"Error fetching page {page_num}: HTTP {res.status}")
            break

        rows = res.css(".view-recherche-offre tbody tr")
        if not rows:
            print(f"No rows found on page {page_num}. Ending pagination.")
            break

        new_count = 0
        for row in rows:
            tds = row.css("td")
            a_tags = row.css("a")
            if not a_tags:
                continue

            link_elem = a_tags[0]
            href = link_elem.attrib.get("href", "")
            full_link = urljoin(BASE_URL, href)
            titre = link_elem.get_all_text().strip()

            if full_link in seen_links:
                continue
            seen_links.add(full_link)
            new_count += 1

            date_pub = tds[0].get_all_text().strip() if len(tds) > 0 else ""
            recruteur = tds[1].get_all_text().strip() if len(tds) > 1 else ""
            recruteur_lines = [line.strip() for line in recruteur.split("\n") if line.strip()]
            recruteur_clean = recruteur_lines[0] if recruteur_lines else ""

            domaine = tds[2].get_all_text().strip() if len(tds) > 2 else ""
            niveau = tds[3].get_all_text().strip() if len(tds) > 3 else ""

            all_offers.append({
                "titre": titre,
                "lien": full_link,
                "date_publication": date_pub,
                "recruteur": recruteur_clean,
                "domaine": domaine,
                "niveau_diplome": niveau,
            })

        print(f"Page {page_num}: {len(rows)} rows, {new_count} new offers extracted (Total so far: {len(all_offers)})")

        pager_next = res.css("li.pager__item--next, li.pager-next, a[rel='next']")
        if not pager_next or len(rows) < 48:
            print("Reached last page.")
            break

        page_num += 1
        time.sleep(1)

    return all_offers


def main() -> None:
    offers = scrape_all_list_offers()
    print(f"\nTotal offers scraped: {len(offers)}")
    out_file = os.path.join(ROOT, "state", "pass_offers_list.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
    print(f"Saved to {out_file}")


if __name__ == "__main__":
    main()
