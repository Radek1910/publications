#!/usr/bin/env python3
# Pobiera WSZYSTKIE prace z publicznego rekordu ORCID (pelne metadane:
# wspolautorzy, typ, data, czasopismo, DOI, URL) i generuje:
#   README.md, publications.bib, publications.ris oraz index.html (GitHub Pages).
import json
import time
import html
import urllib.request
import urllib.error
import datetime

ORCID_ID = "0000-0003-2370-4783"
NAME     = "Radosław Miśkiewicz"
BASE     = "https://pub.orcid.org/v3.0"
HEADERS  = {"Accept": "application/json", "User-Agent": f"orcid-sync ({ORCID_ID})"}
BATCH    = 100

# Mapowanie typu pracy ORCID -> RIS
RIS_TYPE = {
    "journal-article": "JOUR", "book-chapter": "CHAP", "book": "BOOK",
    "conference-paper": "CPAPER", "report": "RPRT", "dataset": "DATA",
    "dissertation-thesis": "THES", "preprint": "GEN", "data-set": "DATA",
}


def fetch(url, retries=4):
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
    cur = node or {}
    for k in keys:
        cur = (cur or {}).get(k) or {}
    if isinstance(cur, dict):
        return (cur.get("value") or "").strip()
    return (cur or "").strip()


def get_put_codes():
    data = fetch(f"{BASE}/{ORCID_ID}/works")
    codes = []
    for g in data.get("group", []):
        summaries = g.get("work-summary") or []
        if summaries and summaries[0].get("put-code") is not None:
            codes.append(summaries[0]["put-code"])
    return codes


def parse_work(w):
    title = first_value(w.get("title"), "title")
    if not title:
        return None
    pd = w.get("publication-date") or {}
    year  = first_value(pd, "year")
    month = first_value(pd, "month")
    day   = first_value(pd, "day")
    journal = first_value(w.get("journal-title"))
    wtype   = (w.get("type") or "").strip()
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
    return {"title": title, "year": year, "month": month, "day": day,
            "journal": journal, "type": wtype, "doi": doi, "url": url,
            "authors": authors}


def link_for(w):
    return (w["doi"] and f"https://doi.org/{w['doi']}") or w["url"] or ""


# ---------- README.md ----------
def write_readme(works, today):
    lines = [f"# Publikacje — {NAME}", "",
             f"ORCID: [{ORCID_ID}](https://orcid.org/{ORCID_ID})  ",
             f"Liczba prac: **{len(works)}** · ostatnia aktualizacja: {today}", ""]
    cur = object()
    for w in works:
        if w["year"] != cur:
            cur = w["year"]
            lines += ["", f"## {cur or 'Bez daty'}", ""]
        authors = ", ".join(w["authors"])
        cite = "- " + (f"{authors}. " if authors else "") + f"**{w['title']}**"
        if w["journal"]:
            cite += f". *{w['journal']}*"
        ty = w["type"].replace("-", " ")
        if ty:
            cite += f" [{ty}]"
        link = link_for(w)
        if link:
            cite += f". {link}"
        lines.append(cite)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------- publications.bib ----------
def write_bib(works):
    bib = []
    for i, w in enumerate(works, 1):
        key = f"miskiewicz{w['year'] or 'nd'}_{i}"
        authors = " and ".join(w["authors"]) if w["authors"] else "Miśkiewicz, Radosław"
        etype = "article" if "journal" in w["type"] else "misc"
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


# ---------- publications.ris ----------
def write_ris(works):
    out = []
    for w in works:
        ty = RIS_TYPE.get(w["type"], "GEN")
        rec = [f"TY  - {ty}"]
        for a in w["authors"]:
            rec.append(f"AU  - {a}")
        if not w["authors"]:
            rec.append("AU  - Miśkiewicz, Radosław")
        rec.append(f"TI  - {w['title']}")
        if w["year"]:
            rec.append(f"PY  - {w['year']}")
            da = w["year"] + (f"/{w['month']}" if w["month"] else "/") + \
                 (f"/{w['day']}" if w["day"] else "/") + "/"
            rec.append(f"DA  - {da}")
        if w["journal"]:
            rec.append(f"T2  - {w['journal']}")
            rec.append(f"JO  - {w['journal']}")
        if w["doi"]:
            rec.append(f"DO  - {w['doi']}")
        link = link_for(w)
        if link:
            rec.append(f"UR  - {link}")
        rec.append("ER  - ")
        out.append("\n".join(rec))
    with open("publications.ris", "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + "\n")


# ---------- index.html (GitHub Pages) ----------
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a2233;--muted:#5b6577;--accent:#2563eb;--line:#e6e9ee}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:32px 20px 64px}
header h1{margin:0 0 4px;font-size:28px}
.sub{color:var(--muted);font-size:15px}
.sub a{color:var(--accent);text-decoration:none}
.controls{position:sticky;top:0;background:var(--bg);padding:16px 0;margin:18px 0 8px;
  border-bottom:1px solid var(--line);display:flex;gap:10px;flex-wrap:wrap}
.controls input,.controls select{padding:9px 12px;border:1px solid var(--line);border-radius:8px;
  font-size:15px;background:#fff;color:var(--ink)}
.controls input{flex:1;min-width:200px}
#count{color:var(--muted);font-size:14px;align-self:center}
h2.year{font-size:15px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
  margin:26px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.pub{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;margin:8px 0}
.pub .t{font-weight:600}
.pub .a{color:var(--muted);font-size:14px;margin-top:2px}
.pub .m{font-size:14px;margin-top:4px}
.pub .m a{color:var(--accent);text-decoration:none}
.badge{display:inline-block;font-size:11px;letter-spacing:.03em;text-transform:uppercase;
  background:#eef2ff;color:#3749b6;border-radius:5px;padding:1px 7px;margin-left:6px;vertical-align:1px}
.hidden{display:none!important}
footer{margin-top:40px;color:var(--muted);font-size:13px;text-align:center}
"""

JS = """
const q=document.getElementById('q'),fy=document.getElementById('fy'),
ft=document.getElementById('ft'),cnt=document.getElementById('count');
function apply(){
  const t=q.value.toLowerCase().trim(),y=fy.value,ty=ft.value;let n=0;
  document.querySelectorAll('.pub').forEach(function(p){
    const okT=!t||p.dataset.text.indexOf(t)>-1;
    const okY=!y||p.dataset.year===y;
    const okTy=!ty||p.dataset.type===ty;
    const show=okT&&okY&&okTy;p.classList.toggle('hidden',!show);if(show)n++;
  });
  document.querySelectorAll('h2.year').forEach(function(h){
    let s=h.nextElementSibling,any=false;
    while(s&&!s.classList.contains('year')){
      if(s.classList.contains('pub')&&!s.classList.contains('hidden'))any=true;
      s=s.nextElementSibling;}
    h.classList.toggle('hidden',!any);
  });
  cnt.textContent=n+' shown';
}
q.addEventListener('input',apply);fy.addEventListener('change',apply);
ft.addEventListener('change',apply);
"""


def write_html(works, today):
    esc = html.escape
    years = sorted({w["year"] for w in works if w["year"]}, reverse=True)
    types = sorted({w["type"].replace("-", " ") for w in works if w["type"]})
    parts = []
    parts.append("<!doctype html><html lang='pl'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    parts.append(f"<title>Publikacje — {esc(NAME)}</title>")
    parts.append(f"<style>{CSS}</style></head><body><div class='wrap'>")
    parts.append("<header>")
    parts.append(f"<h1>Publikacje — {esc(NAME)}</h1>")
    parts.append(f"<div class='sub'>ORCID: <a href='https://orcid.org/{ORCID_ID}' "
                 f"target='_blank' rel='noopener'>{ORCID_ID}</a> · "
                 f"{len(works)} prac · ostatnia aktualizacja: {today}</div>")
    parts.append("</header>")
    # controls
    yopts = "".join(f"<option value='{esc(y)}'>{esc(y)}</option>" for y in years)
    topts = "".join(f"<option value='{esc(t)}'>{esc(t)}</option>" for t in types)
    parts.append("<div class='controls'>")
    parts.append("<input id='q' type='search' placeholder='Szukaj tytulu, autora, czasopisma…'>")
    parts.append(f"<select id='fy'><option value=''>Wszystkie lata</option>{yopts}</select>")
    parts.append(f"<select id='ft'><option value=''>Wszystkie typy</option>{topts}</select>")
    parts.append(f"<span id='count'>{len(works)} shown</span>")
    parts.append("</div>")
    # list
    cur = object()
    for w in works:
        if w["year"] != cur:
            cur = w["year"]
            parts.append(f"<h2 class='year'>{esc(cur or 'Bez daty')}</h2>")
        authors = ", ".join(w["authors"])
        ty = w["type"].replace("-", " ")
        searchable = " ".join([w["title"], authors, w["journal"], ty]).lower()
        link = link_for(w)
        parts.append(f"<div class='pub' data-year='{esc(w['year'])}' "
                     f"data-type='{esc(ty)}' data-text='{esc(searchable)}'>")
        title_html = esc(w["title"])
        if link:
            title_html = (f"<a href='{esc(link)}' target='_blank' "
                          f"rel='noopener'>{esc(w['title'])}</a>")
        badge = f"<span class='badge'>{esc(ty)}</span>" if ty else ""
        parts.append(f"<div class='t'>{title_html}{badge}</div>")
        if authors:
            parts.append(f"<div class='a'>{esc(authors)}</div>")
        meta = []
        if w["journal"]:
            meta.append(f"<em>{esc(w['journal'])}</em>")
        if link:
            meta.append(f"<a href='{esc(link)}' target='_blank' rel='noopener'>{esc(link)}</a>")
        if meta:
            parts.append(f"<div class='m'>{' · '.join(meta)}</div>")
        parts.append("</div>")
    parts.append(f"<footer>Generowane automatycznie z rekordu ORCID · {today}</footer>")
    parts.append(f"<script>{JS}</script>")
    parts.append("</div></body></html>")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write("".join(parts))


def main():
    put_codes = get_put_codes()
    print(f"Znaleziono {len(put_codes)} prac. Pobieram pelne metadane...")
    works = []
    for i in range(0, len(put_codes), BATCH):
        chunk = put_codes[i:i + BATCH]
        url = f"{BASE}/{ORCID_ID}/works/" + ",".join(str(c) for c in chunk)
        for item in fetch(url).get("bulk", []) or []:
            w = item.get("work")
            if w:
                p = parse_work(w)
                if p:
                    works.append(p)
        print(f"  pobrano {min(i + BATCH, len(put_codes))}/{len(put_codes)}")
    works.sort(key=lambda w: (w["year"] or "0", w["month"] or "00",
                              w["title"].lower()), reverse=True)
    today = datetime.date.today().isoformat()
    write_readme(works, today)
    write_bib(works)
    write_ris(works)
    write_html(works, today)
    print(f"Wygenerowano README.md, publications.bib, publications.ris, index.html "
          f"— {len(works)} prac")


if __name__ == "__main__":
    main()
