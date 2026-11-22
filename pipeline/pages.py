"""Build the web pages. The homepage and every case page are plain HTML, written here, so they
load instantly, work without JavaScript and can be read by search engines."""
from __future__ import annotations

import json
from html import escape as esc
from urllib.parse import quote

from . import codebook as cb
from . import export as ex
from .common import ROOT

FONTS = ("https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;"
         "0,8..60,600;0,8..60,700;1,8..60,400;1,8..60,500&family=Inter:wght@400;500;600;700&display=swap")
BEACON = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
          "data-cf-beacon='{\"token\": \"82ab01d233344610a30702e8de41b140\"}'></script>")
ICON_DOWNLOAD = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 '
                 '2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>')
ICON_SEARCH = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
               '<line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>')
ORG = {"@type": "Organization", "@id": "https://crimconsortium.com/#org", "name": "CrimConsortium",
       "url": "https://crimconsortium.com/"}


def shell(cfg: dict, *, path: str, title: str, description: str, body: str, root: str = "",
          narrow: bool = True, current: str = "", jsonld: list | None = None, scripts: str = "",
          og_type: str = "website") -> str:
    site = cfg["site"]
    url = site["url"] + path
    image = site["url"] + "og-image.png"
    ld = ""
    if jsonld:
        ld = ('\n    <script type="application/ld+json">'
              + json.dumps({"@context": "https://schema.org", "@graph": jsonld}, ensure_ascii=False)
              .replace("</", "<\\/") + "</script>")

    def nav(href, label, key, extra=""):
        cur = ' aria-current="page"' if current == key else ""
        return f'<a href="{root}{href}"{cur}{extra}>{label}</a>'

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(description)}" />
    <meta name="author" content="CrimConsortium" />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <meta name="theme-color" content="#0e0e0e" />
    <link rel="canonical" href="{esc(url)}" />

    <meta property="og:title" content="{esc(title)}" />
    <meta property="og:description" content="{esc(description)}" />
    <meta property="og:type" content="{og_type}" />
    <meta property="og:url" content="{esc(url)}" />
    <meta property="og:site_name" content="{esc(site['name'])}" />
    <meta property="og:locale" content="en_US" />
    <meta property="og:image" content="{esc(image)}" />
    <meta property="og:image:type" content="image/png" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta property="og:image:alt" content="{esc(site['name'])}: incidents where self-driving is in question" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:site" content="@CrimConsortium" />
    <meta name="twitter:title" content="{esc(title)}" />
    <meta name="twitter:description" content="{esc(description)}" />
    <meta name="twitter:image" content="{esc(image)}" />

    <link rel="icon" type="image/x-icon" href="{root}favicon.ico" />
    <link rel="dns-prefetch" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="{FONTS}" rel="stylesheet" />
    <link rel="stylesheet" href="{root}style.css" />
    <script>
      (function () {{
        var t = null;
        try {{ t = localStorage.getItem("sdi-theme"); }} catch (e) {{}}
        if (!t) t = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", t);
      }})();
    </script>{ld}
  </head>
  <body>
    <a class="skip-link" href="#main">Skip to content</a>
    <div class="page{' page-narrow' if narrow else ''}">
      <header class="site-header">
        <div class="brand">
          <a class="brand-link" href="https://crimconsortium.com" target="_blank" rel="noopener" aria-label="CrimConsortium">
            <img class="brand-mark" src="{root}crimconsortium-logo.png" alt="CrimConsortium" width="36" height="36" />
          </a>
          <div class="brand-text">
            <a class="brand-title brand-title-link" href="{root}index.html">{esc(site['name'])}</a>
          </div>
        </div>
        <div class="header-actions">
          <nav class="site-nav" aria-label="Site">
            {nav("search.html", "Search", "search")}
            {nav("about.html", 'About<span class="nav-extra">&nbsp;the data</span>', "about")}
          </nav>
          <button class="icon-btn" type="button" data-theme-toggle aria-label="Toggle color scheme" title="Toggle light or dark"></button>
        </div>
      </header>

      <main id="main">
{body}
      </main>

      <footer class="site-footer">
        <div class="footer-note">
          Compiled from published news reports found through Google News and Bing News searches, refreshed daily.
          Coded values are drafted by a language model from those reports and are not yet reviewed by a person;
          each one links to the passage it rests on. A count of incidents is not a rate, and a mention of an
          automated-driving feature is not a finding that it was in use. Verify every case at its sources.
          <br><br>
          Provided by <a href="https://crimconsortium.com" target="_blank" rel="noopener">CrimConsortium</a>.
          Read open-access criminology on <a href="https://www.crimrxiv.com" target="_blank" rel="noopener">CrimRxiv</a>.
          Data licensed <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>;
          source code on <a href="{esc(site['repo'])}" target="_blank" rel="noopener">GitHub</a>.
          Corrections and suggestions: <a href="mailto:{esc(site['contact_email'])}">{esc(site['contact_email'])}</a>.
        </div>
        <p class="footer-credit">A project of Scott Jacques and Miranda Baumann. Miranda drives a Tesla.</p>
      </footer>
    </div>
    <script src="{root}site.js" defer></script>{scripts}
    {BEACON}
  </body>
</html>
"""


# --------------------------------------------------------------------------- shared pieces

def incident_item(v: dict, root: str = "") -> str:
    tags = "".join(f'<span class="tag{" tag-status" if t["kind"] == "status" else ""}">{esc(t["label"])}</span>'
                   for t in v["tags"])
    newest_first = sorted(v["sources"], key=lambda s: s["published"], reverse=True)
    seen, links = set(), []
    for s in newest_first:
        if s["publisher"] not in seen:
            seen.add(s["publisher"])
            links.append(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["publisher"])}</a>')
    shown, extra = links[:3], len(links) - 3
    src = ", ".join(shown) + (f", and {extra} more" if extra > 0 else "")
    summary = ""
    if v["summary"]:
        by = f'{esc(v["summary_by"])}' if v["summary_kind"] == "publisher" else "Machine-drafted summary"
        summary = (f'<p class="incident-summary">{esc(v["summary"])} '
                   f'<span class="incident-by">({by})</span></p>')
    return f"""          <li class="incident">
            <div class="incident-eyebrow"><span class="incident-lead">{esc(v["lead"])}</span><span class="incident-date">{esc(v["date_label"])}</span></div>
            <h3 class="incident-title"><a href="{root}{v["url"]}">{esc(v["title"])}</a></h3>
            {summary}
            <div class="incident-tags">{tags}</div>
            <div class="incident-foot"><span>Reported by {src}</span><a class="incident-more" href="{root}{v["url"]}" aria-label="Full record for {v["id"]}">Full record</a></div>
          </li>"""


def dataset_ld(cfg: dict, updated: str, n_cases: int, first: str) -> dict:
    u = cfg["site"]["url"]
    return {
        "@type": "Dataset", "@id": u + "#dataset", "name": cfg["site"]["name"],
        "alternateName": "CrimConsortium dataset of incidents involving automated driving",
        "description": ("An open dataset of crashes, near misses, police stops and court cases in which a vehicle's "
                        "automated-driving feature (such as Tesla Autopilot or Full Self-Driving) is claimed, "
                        "questioned or confirmed to be involved. One case per incident, built from published "
                        f"reports, with {len(cb.VARIABLES)} coded variables, supporting quotations and source links. "
                        f"{n_cases} case{'s' if n_cases != 1 else ''} as of {updated}."),
        "url": u, "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
        "dateModified": updated, "temporalCoverage": f"{first}/..", "inLanguage": "en",
        "keywords": ["self-driving cars", "automated driving", "Tesla Autopilot", "Full Self-Driving", "robotaxi",
                     "traffic incidents", "criminology", "open data"],
        "creator": ORG, "publisher": ORG,
        "variableMeasured": [v["label"] for v in cb.VARIABLES],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/zip", "contentUrl": u + "data/self-driving-incidents.zip"},
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": u + "data/cases.csv"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": u + "data/cases.json"}],
    }


# --------------------------------------------------------------------------- homepage

def home(pairs, cfg, updated, n_reports) -> str:
    site = cfg["site"]
    n = int(site.get("homepage_count", 25))
    latest = [v for _, v in pairs[:n]]
    items = "\n".join(incident_item(v) for v in latest)
    total = len(pairs)
    mail = esc(site["contact_email"])
    if not latest:
        items = '          <li class="incident"><p class="incident-summary">The first cases are being coded and will appear here shortly.</p></li>'
    body = f"""        <section class="hero">
          <div class="hero-eyebrow">A dataset provided by <a href="https://crimconsortium.com" target="_blank" rel="noopener">CrimConsortium</a> · Last updated {ex.nice_date(updated)}</div>
          <h1 class="hero-title">Incidents where self-driving is <em>in question</em>.</h1>
          <p class="hero-lead">
            An open dataset of crashes, near misses, police stops and court cases in which a vehicle's
            automated-driving feature is claimed, questioned or confirmed to be involved. Each incident is one
            case, built from published reports and coded for what happened and who says so. The dataset
            covers Tesla for now.
          </p>
          <p class="notice">
            We're iteratively improving this site and dataset. Please email corrections or suggestions to
            <a href="mailto:{mail}">{mail}</a>.
          </p>
        </section>

        <section class="stats" aria-label="Dataset summary">
          <div><div class="stat-value">{total:,}</div><div class="stat-label">Cases</div></div>
          <div><div class="stat-value">{n_reports:,}</div><div class="stat-label">Reports linked</div></div>
          <div><div class="stat-value">{len(cb.VARIABLES)}</div><div class="stat-label">Coded variables</div></div>
          <div><div class="stat-value">{ex.nice_date(updated, short=True)}</div><div class="stat-label">Data compiled</div></div>
        </section>

        <div class="download-row">
          <a class="btn-primary" href="data/self-driving-incidents.zip" download>{ICON_DOWNLOAD}<span>Download the dataset</span></a>
          <span class="download-alt">One .zip with every file. Or take
            <a href="data/cases.csv" download>cases.csv</a>,
            <a href="data/cases.json" download>cases.json</a>, or read the
            <a href="about.html#codebook">codebook</a>.</span>
        </div>

        <section aria-labelledby="latest-title">
          <div class="section-head"><h2 class="section-title" id="latest-title">Latest incidents</h2></div>
          <p class="section-note">
            The {min(n, total) if total else n} most recent, newest first. Each summary is the publisher's own words.
            Labels record what coverage says, not what has been established, and the coding behind
            them is machine-drafted and not yet reviewed.
          </p>
          <ol class="incident-list">
{items}
          </ol>
        </section>

        <section class="search-panel" aria-labelledby="search-title">
          <h2 id="search-title">Search the full dataset</h2>
          <p>Look through {'all ' + format(total, ',') + ' cases' if total != 1 else 'every case'} by place, vehicle, feature, publisher or any word in the record.</p>
          <form class="search-form" action="search.html" method="get" role="search">
            <label class="search-bar">
              {ICON_SEARCH}
              <span class="skip-link">Search cases</span>
              <input type="search" name="q" placeholder="Try &ldquo;Texas&rdquo;, &ldquo;Cybertruck&rdquo; or &ldquo;asleep&rdquo;" autocomplete="off" />
            </label>
            <button class="btn-primary" type="submit">Search</button>
          </form>
          <p class="browse-all"><a class="text-link" href="search.html">Browse and filter all cases</a></p>
        </section>"""
    first = min((v["first"] for _, v in pairs), default=updated)
    ld = [dataset_ld(cfg, updated, total, first), ORG,
          {"@type": "WebSite", "@id": site["url"] + "#website", "url": site["url"], "name": site["name"],
           "publisher": {"@id": ORG["@id"]},
           "potentialAction": {"@type": "SearchAction", "target": site["url"] + "search.html?q={search_term_string}",
                               "query-input": "required name=search_term_string"}}]
    return shell(cfg, path="", current="home", jsonld=ld, body=body,
                 title=f"{site['name']}: open data on Tesla Autopilot and FSD incidents",
                 description=("Open dataset of crashes, near misses, police stops and court cases in which Tesla "
                              "Autopilot, Full Self-Driving or another automated-driving feature is in question. "
                              "Coded from published reports. Free download. From CrimConsortium."))


# --------------------------------------------------------------------------- case page

def _value_cell(var, vals, evidence) -> str:
    name = var["name"]
    if name not in vals:
        return '<span class="var-value var-empty">Not stated in the reports read</span>'
    val = vals[name]
    shown = ex.nice_date(val) if var["kind"] == "date" else ex.human(val)
    out = f'<span class="var-value">{esc(shown)}</span>'
    e = evidence.get(name)
    if e:
        out += (f'<div class="var-quote">&ldquo;{esc(e["quote"])}&rdquo; '
                f'<a href="{esc(e["source_url"])}" target="_blank" rel="noopener">source</a></div>')
    return out


def case_page(case, v, cfg) -> str:
    site = cfg["site"]
    coding = case.get("coding") or {}
    vals, evidence = coding.get("values", {}), coding.get("evidence", {})
    root = "../"
    groups, order = {}, []
    for var in cb.VARIABLES:
        if var["group"] not in groups:
            groups[var["group"]] = []
            order.append(var["group"])
        groups[var["group"]].append(var)
    tables = ""
    for g in order:
        rows = "".join(f'<tr><th scope="row">{esc(var["label"])}<code>{var["name"]}</code></th>'
                       f'<td>{_value_cell(var, vals, evidence)}</td></tr>' for var in groups[g])
        tables += f'<div class="var-group"><h3>{esc(g)}</h3><table class="var-table"><tbody>{rows}</tbody></table></div>'
    claims = "".join(
        f'<li class="claim"><div class="claim-who">{esc(ex.human(c["claimant"]))} · {esc(ex.human(c["topic"]))}</div>'
        f'<div class="claim-text">{esc(c["paraphrase"])}</div>'
        f'<div class="var-quote">&ldquo;{esc(c["quote"])}&rdquo; '
        f'<a href="{esc(c["source_url"])}" target="_blank" rel="noopener">source</a></div></li>'
        for c in coding.get("claims", []))
    read = {r["url"]: r["basis"] for r in coding.get("sources_read", [])}
    basis_label = {"full_text": "article text read by the coder", "summary": "summary read by the coder",
                   "headline": "headline read by the coder"}
    sources = "".join(
        f'<li><div class="source-title"><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["title"])}</a></div>'
        f'<div class="source-meta">{esc(s["publisher"])} · {ex.nice_date(s["published"][:10])}'
        + (f' · {basis_label[read[s["url"]]]}' if s["url"] in read else "") + "</div></li>"
        for s in sorted(v["sources"], key=lambda s: s["published"], reverse=True))
    summary = ""
    if case.get("source_summary"):
        summary = (f'<blockquote class="source-quote"><p>{esc(case["source_summary"])}</p>'
                   f'<footer>Publisher\'s summary, {esc(case["source_summary_publisher"])}</footer></blockquote>')
    narrative = (f'<div class="prose"><p>{esc(v["narrative"])}</p></div>' if v["narrative"] else "")
    mail = site["contact_email"]
    subject = quote(f"Correction for {v['id']}")
    tags = "".join(f'<span class="tag{" tag-status" if t["kind"] == "status" else ""}">{esc(t["label"])}</span>' for t in v["tags"])
    n = len(v["sources"])
    removed = coding.get("unsupported_values_removed", 0)
    url = site["url"] + v["url"]
    body = f"""        <nav class="crumbs" aria-label="Breadcrumb"><a href="{root}index.html">Latest incidents</a> / <span class="case-id">{v["id"]}</span></nav>
        <header class="case-head">
          <div class="incident-eyebrow"><span class="incident-lead">{esc(v["lead"])}</span><span class="incident-date">{esc(v["date_label"])}</span></div>
          <h1>{esc(v["title"])}</h1>
          <p class="case-meta">Headline from {esc(v["publisher"])} · {n} report{"s" if n != 1 else ""} · first reported {ex.nice_date(v["first"])} · record updated {ex.nice_date(case["updated"][:10])}</p>
          <div class="incident-tags" style="margin-top: var(--space-4)">{tags}</div>
          <p class="review-flag"><span><strong>Machine-coded, not yet reviewed.</strong> Spot a mistake? <a class="text-link" href="mailto:{esc(mail)}?subject={subject}">Email a correction</a>.</span></p>
        </header>

        <section class="case-section" aria-labelledby="s-what">
          <h2 id="s-what">What coverage reports</h2>
          {narrative}
          {('<p class="section-note" style="margin-top: var(--space-2)">Machine-drafted from the reports listed below.</p>') if v["narrative"] else ""}
          {summary}
        </section>

        <section class="case-section" aria-labelledby="s-vars">
          <h2 id="s-vars">Coded variables</h2>
          <p class="section-note">Each value is followed by the passage it rests on. &ldquo;Not stated&rdquo; means the reports read did not say; it does not mean no. Definitions are in the <a class="text-link" href="{root}about.html#codebook">codebook</a>.</p>
          {tables}
        </section>

        {f'<section class="case-section" aria-labelledby="s-claims"><h2 id="s-claims">Who says what</h2><ul class="claim-list">{claims}</ul></section>' if claims else ""}

        <section class="case-section" aria-labelledby="s-sources">
          <h2 id="s-sources">Sources</h2>
          <ul class="source-list">{sources}</ul>
        </section>

        <section class="case-section" aria-labelledby="s-record">
          <h2 id="s-record">About this record</h2>
          <div class="cite-box">
            <p>Coded by {esc(coding.get("coder") or "")} on {ex.nice_date((coding.get("coded_at") or "")[:10])}, codebook version {esc(coding.get("codebook_version") or "")}.
            {removed} proposed value{"s were" if removed != 1 else " was"} removed because the supporting passage could not be found in the report.</p>
            <p style="margin-top: var(--space-2)">Cite as: CrimConsortium. {esc(site["name"])}, case {v["id"]}. {esc(url)}</p>
          </div>
        </section>

        <div class="case-actions">
          <a class="btn-primary" href="mailto:{esc(mail)}?subject={subject}">Report a correction</a>
          <a class="btn-secondary" href="{root}data/self-driving-incidents.zip" download>Download the dataset</a>
          <a class="btn-secondary" href="{root}search.html">Search all cases</a>
        </div>"""
    desc = (v["narrative"] or case.get("source_summary") or v["title"])[:300]
    ld = [{"@type": "WebPage", "@id": url, "url": url, "name": f"{v['id']}: {v['title']}",
           "description": desc, "dateModified": case["updated"][:10],
           "isPartOf": {"@type": "Dataset", "@id": site["url"] + "#dataset", "name": site["name"], "url": site["url"]},
           "publisher": {"@id": ORG["@id"]},
           "citation": [s["url"] for s in v["sources"][:10]]},
          ORG,
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": site["name"], "item": site["url"]},
              {"@type": "ListItem", "position": 2, "name": v["id"], "item": url}]}]
    return shell(cfg, path=v["url"], root=root, jsonld=ld, body=body, og_type="article",
                 title=f"{v['lead'] or v['id']}: {v['title']}"[:110] + f" | {v['id']}",
                 description=desc)


# --------------------------------------------------------------------------- search page

def search_page(cfg, total) -> str:
    site = cfg["site"]
    body = f"""        <header class="page-head">
          <h1>Search the dataset</h1>
          <p>{'All ' + format(total, ',') + ' cases' if total != 1 else 'Every case'}. Type any word, or narrow with the filters. Labels record what coverage says, not what has been established.</p>
        </header>
        <div class="workspace">
          <aside class="sidebar" aria-label="Filters">
            <div class="panel">
              <div class="panel-title">Filters</div>
              <div class="filter-group"><span class="filter-label">Feature named in coverage</span><div class="checkbox-list" id="f-system"></div></div>
              <div class="filter-group"><span class="filter-label">Was it in use?</span><div class="checkbox-list" id="f-status"></div></div>
              <div class="filter-group"><span class="filter-label">Type of incident</span><div class="checkbox-list" id="f-type"></div></div>
              <div class="filter-group"><span class="filter-label">Harm</span><div class="checkbox-list" id="f-deaths"></div></div>
              <div class="filter-group"><span class="filter-label">State or region</span><div class="dept-list" id="f-state"></div></div>
              <div class="filter-group"><span class="filter-label">Year</span><div class="checkbox-list" id="f-year"></div></div>
              <button class="clear-btn" id="clear-filters" type="button">Clear all filters</button>
            </div>
          </aside>
          <div class="main">
            <label class="search-bar">
              {ICON_SEARCH}
              <span class="skip-link">Search cases</span>
              <input type="search" id="search-input" placeholder="Search by place, vehicle, feature, publisher or keyword" autocomplete="off" spellcheck="false" />
            </label>
            <div class="active-filters" id="active-filters"></div>
            <div class="results-header">
              <div class="results-title-wrap">
                <h2 class="results-title" id="results-title">All cases</h2>
                <div class="results-meta" id="results-meta" aria-live="polite"></div>
              </div>
              <div class="sort-control">
                <label for="sort-select" class="sort-label">Sort by</label>
                <select id="sort-select">
                  <option value="new">Newest incident</option>
                  <option value="old">Oldest incident</option>
                  <option value="reports">Most reports</option>
                </select>
              </div>
            </div>
            <ol class="incident-list results-list" id="results"></ol>
            <div class="empty-state" id="empty-state" hidden>
              <h3>No matching cases</h3>
              <p>Try a different word, or clear the filters.</p>
            </div>
            <div class="pager"><button class="btn-secondary" id="more" type="button" hidden>Show more</button></div>
            <noscript><p class="section-note">Search needs JavaScript. Without it, you can still <a class="text-link" href="data/cases.csv">download every case as a CSV file</a>.</p></noscript>
          </div>
        </div>"""
    return shell(cfg, path="search.html", narrow=False, current="search", body=body,
                 scripts='\n    <script src="data/site-data.js" defer></script>\n    <script src="search.js" defer></script>',
                 title=f"Search cases | {site['name']}",
                 description="Search and filter every case in the dataset by place, vehicle, automated-driving "
                             "feature, whether it was reported in use, type of incident and year.")


# --------------------------------------------------------------------------- about page

def codebook_html() -> str:
    out, group = [], None
    for v in cb.VARIABLES:
        if v["group"] != group:
            group = v["group"]
            out.append(f"<h3>{esc(group)}</h3>")
        kind = {"enum": "one value", "multi": "one or more values", "int": "whole number",
                "text": "short text", "date": "date"}[v["kind"]]
        vals = ""
        if v.get("values"):
            vals = "<dl>" + "".join(f"<dt><code>{k}</code></dt><dd>{esc(d or ex.human(k) + '.')}</dd>"
                                    for k, d in v["values"].items()) + "</dl>"
        out.append(f'<details><summary><span>{esc(v["label"])}</span><code>{v["name"]}</code></summary>'
                   f'<div class="cb-body"><p>{esc(v["desc"])} <em>({kind})</em></p>{vals}</div></details>')
    return "\n".join(out)


def about_page(cfg, total, updated) -> str:
    site = cfg["site"]
    mail = esc(site["contact_email"])
    body = f"""        <header class="page-head">
          <h1>About the data</h1>
          <p>What this dataset is, how each case is found and coded, what it cannot tell you, and how to use and cite it.</p>
        </header>
        <div class="prose">
          <p class="notice" style="margin-top: 0">We're iteratively improving this site and dataset. Please email corrections or suggestions to <a href="mailto:{mail}">{mail}</a>.</p>

          <h2>What it is</h2>
          <p>A case is one incident in which a vehicle's automated-driving feature is claimed, questioned or confirmed to be involved: a crash, a near miss, a police stop, a person found asleep at the wheel, or a court case about any of these. Incidents with no collision are included. The dataset covers Tesla (Autopilot, Full Self-Driving, Summon and its robotaxi service) for now, and is built so other makers can be added.</p>
          <p>It is meant for research and teaching in criminology and related fields: who is said to have done what, how police, prosecutors, regulators and courts respond, and how responsibility is attributed when a machine shares the driving.</p>

          <h2>How cases are found</h2>
          <p>Once a day, a program searches Google News and Bing News for reports that name an automated-driving feature and describe something that happened. Reports about the same event are grouped into one case, and later reports (an arrest, a lawsuit, a verdict) are attached to the case they belong to. Round-ups of several incidents, statistics, product news and opinion pieces are set aside and listed, with the reason, in <code>screened_out.csv</code>.</p>

          <h2>How cases are coded</h2>
          <p>A language model reads the reports attached to a case (the article text where the publisher allows it, otherwise the headline and summary) and drafts the coded variables, a short neutral narrative, and a list of who said what. Three rules limit what it can assert:</p>
          <ul>
            <li>It may use only the reports attached to the case.</li>
            <li>Every coded value must come with a quotation, and the program keeps the value only if that quotation is found word for word in the report. Values that fail are removed and counted on the case page.</li>
            <li>A mention of a feature is never treated as evidence that it was in use. The variable <code>engagement_status</code> separates what an official source or the maker's own data states from what a driver, lawyer or witness claims.</li>
          </ul>
          <p>Every record is marked &ldquo;{esc(cb.REVIEW_STATUS)}&rdquo; until a person has checked it. Summaries shown on the homepage are each publisher's own words, not ours.</p>

          <h2>What it cannot tell you</h2>
          <ul>
            <li><strong>It is not a count of all incidents.</strong> It holds only incidents that reached published news in English and that our searches found. Many incidents are never reported.</li>
            <li><strong>Counts are not rates.</strong> Nothing here says how often these features are used without incident, so the data cannot show whether they are safer or less safe than a human driver.</li>
            <li><strong>It does not establish fault or cause.</strong> It records what coverage reports and who says so.</li>
            <li><strong>Machine coding makes mistakes.</strong> Dates, places and counts can be wrong, and two cases may turn out to be the same event. Check the linked sources before relying on a record.</li>
            <li><strong>Coverage changes.</strong> Early reports are often revised. A case reflects the reports attached to it on the date shown.</li>
          </ul>

          <h2>Privacy</h2>
          <p>Coded fields, narratives and claims describe people by role (&ldquo;the driver&rdquo;, &ldquo;a passenger&rdquo;) and do not name private individuals. Names may still appear in publishers' headlines and in the linked reports. We store links and short quotations, not copies of articles. To ask for a change, email <a href="mailto:{mail}">{mail}</a>.</p>

          <h2>Download, licence and citation</h2>
          <p><a href="data/self-driving-incidents.zip" download>Download everything as one .zip</a>, or take single files: <a href="data/cases.csv" download>cases.csv</a>, <a href="data/evidence.csv" download>evidence.csv</a>, <a href="data/claims.csv" download>claims.csv</a>, <a href="data/sources.csv" download>sources.csv</a>, <a href="data/screened_out.csv" download>screened_out.csv</a>, <a href="data/cases.json" download>cases.json</a>, <a href="data/codebook.json" download>codebook.json</a>.</p>
          <p>The data are free to reuse under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>. The code that builds them is on <a href="{esc(site['repo'])}" target="_blank" rel="noopener">GitHub</a>, where every change to the data is recorded.</p>
          <p>Cite as: CrimConsortium. <em>{esc(site['name'])}</em> [dataset]. {esc(site['url'])} (data as of {ex.nice_date(updated)}; codebook version {cb.VERSION}).</p>

          <h2 id="codebook">Codebook, version {cb.VERSION}</h2>
          <p>{len(cb.VARIABLES)} coded variables. Select one to see its definition and allowed values. A blank value means the reports read did not state it.</p>
        </div>
        <div class="codebook">
{codebook_html()}
        </div>"""
    return shell(cfg, path="about.html", current="about", body=body,
                 title=f"About the data and codebook | {site['name']}",
                 description="How the Self-Driving Incidents Explorer finds and codes cases, what the data can and "
                             "cannot show, the full codebook, licence and citation.")


# --------------------------------------------------------------------------- write

def write_pages(pairs, cfg, updated, n_reports) -> None:
    site = cfg["site"]
    total = len(pairs)
    ex.write_if_changed(ROOT / "index.html", home(pairs, cfg, updated, n_reports))
    ex.write_if_changed(ROOT / "search.html", search_page(cfg, total))
    ex.write_if_changed(ROOT / "about.html", about_page(cfg, total, updated))
    for case, v in pairs:
        ex.write_if_changed(ROOT / v["url"], case_page(case, v, cfg))
    urls = [(site["url"], updated, "daily", "1.0"), (site["url"] + "search.html", updated, "daily", "0.8"),
            (site["url"] + "about.html", updated, "monthly", "0.7")]
    urls += [(site["url"] + v["url"], c["updated"][:10], "monthly", "0.6") for c, v in pairs]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"  <url><loc>{esc(u)}</loc><lastmod>{d}</lastmod><changefreq>{f}</changefreq><priority>{p}</priority></url>"
            for u, d, f, p in urls]
    ex.write_if_changed(ROOT / "sitemap.xml", "\n".join(xml + ["</urlset>"]) + "\n")
    ex.write_if_changed(ROOT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site['url']}sitemap.xml\n")
