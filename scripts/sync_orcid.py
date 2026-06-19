#!/usr/bin/env python3
# Pobiera WSZYSTKIE prace z publicznego rekordu ORCID (pełne metadane:
# współautorzy, typ, data, czasopismo, DOI, URL) i generuje README.md
# oraz publications.bib.
import json
import time
import urllib.request
import urllib.error
import datetime

ORCID_ID = "0000-0003-2370-4783"
NAME     = "Radosław Miśkiewicz"
BASE     = "https://pub.orcid.org/v3.0"
# ORCID odrzuca domyślny User-Agent urllib — ustawiamy własny.
HEADERS  = {"Accept": "application/json", "User-Agent": f"orcid-sync ({ORCID_ID})"}
BATCH    = 100  # endpoint zbiorczy /works/{kody} przyjmuje do 100 kodow naraz


def fetch(url, retries=4):
    """Pobiera JSON z prostym ponawianiem przy bledach sieci/limitow."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            wait = 2 ** attempt
            print(f"  ! blad ({e}); ponawiam za {wait}s [{attempt + 1}/{retries}]")
            time.sleep(wait)
    raise SystemExit(f"Nie udalo sie pobrac: {url}\n{last}")


def first_value(node, *keys):
    """Bezpiecznie wyciaga zagniezdzona wartosc {'value': ...}."""
    cur = node or {}
    for k in keys:
        cur = (cur or {}).get(k) or {}
    if isinstance(cur, dict):
        return (cur.get("value") or "").strip()
    return (cur or "").strip()


def get_put_codes():
    """Zwraca preferowany put-code dla kazdej (zgrupowanej) pracy."""
    data = fetch(f"{BASE}/{ORCID_ID}/works")
    codes = []
    for g in data.get("group", []):
        summaries = g.get("work-summary") or []
        if summaries and summaries[0].get("put-code") is not None:
            codes.append(summaries[0]["put-code"])
    return codes


def parse_work(w):
    """Mapuje pelny rekord pracy na ujednolicony slownik."""
    title = first_value(w.get("title"), "title")
    if not title:
        return None

    pd = w.get("publication-date") or {}
    year  = first_value(pd, "year")
    month = first_value(pd, "month")
    day   = first_value(pd, "day")

    journal = first_value(w.get("journal-title"))
    wtype   = (w.get("type") or "").replace("-", " ").strip()
    url     = first_value(w.get("url"))

    doi = ""
    for eid in (w.get("external-ids") or {}).get("external-id", []) or []:
        if eid.get("external-id-type") == "doi":
            doi = (eid.get("external-id-value") or "").strip()
            break

    authors = []
    for c in (w.get("contributors") or {}).get("contributor", []) or []:
        name = first_value(c.get("credit-name"))
        if name:
            authors.append(name)

    return {
        "title": title, "year": year, "month": month, "day": day,
        "journal": journal, "type": wtype, "doi": doi, "url": url,
        "authors": authors,
    }


def main():
    put_codes = get_put_codes()
    print(f"Znaleziono {len(put_codes)} prac w rekordzie ORCID. "
          f"Pobieram pelne metadane...")

    works = []
    for i in range(0, len(put_codes), BATCH):
        chunk = put_codes[i:i + BATCH]
        url = f"{BASE}/{ORCID_ID}/works/" + ",".join(str(c) for c in chunk)
        bulk = fetch(url)
        for item in bulk.get("bulk", []) or []:
            w = item.get("work")
            if not w:
                continue
            parsed = parse_work(w)
            if parsed:
                works.append(parsed)
        print(f"  pobrano {min(i + BATCH, len(put_codes))}/{len(put_codes)}")

    works.sort(key=lambda w: (w["year"] or "0", w["month"] or "00",
                              w["title"].lower()), reverse=True)

    today = datetime.date.today().isoformat()

    # --- README.md ---
    lines = [
        f"# Publikacje — {NAME}", "",
        f"ORCID: [{ORCID_ID}](https://orcid.org/{ORCID_ID})  ",
        f"Liczba prac: **{len(works)}** · ostatnia aktualizacja: {today}", "",
    ]
    cur = object()
    for w in works:
        if w["year"] != cur:
            cur = w["year"]
            lines += ["", f"## {cur or 'Bez daty'}", ""]
        authors = ", ".join(w["authors"])
        cite = "- "
        if authors:
            cite += f"{authors}. "
        cite += f"**{w['title']}**"
        if w["journal"]:
            cite += f". *{w['journal']}*"
        if w["type"]:
            cite += f" [{w['type']}]"
        link = (w["doi"] and f"https://doi.org/{w['doi']}") or w["url"]
        if link:
            cite += f". {link}"
        lines.append(cite)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # --- publications.bib ---
    bib = []
    for i, w in enumerate(works, 1):
        key = f"miskiewicz{w['year'] or 'nd'}_{i}"
        authors = " and ".join(w["authors"]) if w["authors"] else "Miśkiewicz, Radosław"
        etype = "article" if "journal" in (w["type"] or "") else "misc"
        entry = [f"@{etype}{{{key},",
                 f"  author  = {{{authors}}},",
                 f"  title   = {{{w['title']}}},"]
        if w["year"]:
            entry.append(f"  year    = {{{w['year']}}},")
        if w["journal"]:
            entry.append(f"  journal = {{{w['journal']}}},")
        if w["doi"]:
            entry.append(f"  doi     = {{{w['doi']}}},")
        if w["url"] and not w["doi"]:
            entry.append(f"  url     = {{{w['url']}}},")
        if w["type"]:
            entry.append(f"  note    = {{{w['type']}}},")
        entry.append("}")
        bib.append("\n".join(entry))
    with open("publications.bib", "w", encoding="utf-8") as f:
        f.write("\n\n".join(bib) + "\n")

    print(f"Wygenerowano README.md i publications.bib — {len(works)} prac")


if __name__ == "__main__":
    main()
