#!/usr/bin/env python3
# Pobiera prace z publicznego rekordu ORCID i generuje README.md + publications.bib
import json, urllib.request, datetime

ORCID_ID = "0000-0003-2370-4783"
NAME     = "Radosław Miśkiewicz"
BASE     = "https://pub.orcid.org/v3.0"

def fetch(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    data = fetch(f"{BASE}/{ORCID_ID}/works")
    works = []
    for g in data.get("group", []):
        ws = g.get("work-summary", [{}])[0]
        title = (ws.get("title") or {}).get("title", {}).get("value", "").strip()
        if not title: continue
        pd = ws.get("publication-date") or {}
        year = ((pd.get("year") or {}) or {}).get("value", "") if pd else ""
        jt = ws.get("journal-title") or {}
        journal = jt.get("value", "") if jt else ""
        doi = ""
        for eid in (ws.get("external-ids") or {}).get("external-id", []):
            if eid.get("external-id-type") == "doi":
                doi = eid.get("external-id-value", ""); break
        works.append({"title": title, "year": year,
                      "journal": journal, "doi": doi})
    works.sort(key=lambda w: w["year"] or "0", reverse=True)

    # --- README.md ---
    today = datetime.date.today().isoformat()
    lines = [f"# Publikacje — {NAME}", "",
             f"ORCID: [{ORCID_ID}](https://orcid.org/{ORCID_ID})  ",
             f"Liczba prac: **{len(works)}** · ostatnia aktualizacja: {today}", ""]
    cur = None
    for w in works:
        if w["year"] != cur:
            cur = w["year"]; lines += ["", f"## {cur or 'Bez daty'}", ""]
        cite = f"- **{w['title']}**"
        if w["journal"]: cite += f". *{w['journal']}*"
        if w["doi"]:    cite += f". https://doi.org/{w['doi']}"
        lines.append(cite)
    open("README.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # --- publications.bib ---
    bib = []
    for i, w in enumerate(works, 1):
        key = f"miskiewicz{w['year'] or 'nd'}_{i}"
        entry = [f"@article{{{key},",
                 f"  author = {{Mi{{\\'s}}kiewicz, Rados{{\\l}}aw}},",
                 f"  title  = {{{w['title']}}},"]
        if w["year"]:    entry.append(f"  year   = {{{w['year']}}},")
        if w["journal"]: entry.append(f"  journal= {{{w['journal']}}},")
        if w["doi"]:     entry.append(f"  doi    = {{{w['doi']}}},")
        entry.append("}"); bib.append("\n".join(entry))
    open("publications.bib", "w", encoding="utf-8").write("\n\n".join(bib) + "\n")
    print(f"Wygenerowano README.md i publications.bib — {len(works)} prac")

if __name__ == "__main__":
    main()
