"""Build the web pages. The homepage and every case page are plain HTML, written here, so they
load instantly, work without JavaScript and can be read by search engines."""
from __future__ import annotations

import json
from html import escape as esc
from urllib.parse import quote

from . import cluster
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
          og_type: str = "website", canonical: str | None = None) -> str:
    site = cfg["site"]
    url = site["url"] + path
    # A page that only points elsewhere (a retired case ID) is kept out of search engines.
    robots = "noindex, follow" if canonical else "index, follow, max-image-preview:large"
    link = canonical or url
    image = site["url"] + "og-image.png?v=2"
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
    <meta name="robots" content="{robots}" />
    <meta name="theme-color" content="#0e0e0e" />
    <link rel="canonical" href="{esc(link)}" />

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
    <meta property="og:image:alt" content="{esc(site['name'])}: self-driving incidents, claimed, questioned, confirmed" />
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
    <link rel="stylesheet" href="{root}style.css?v=4" />
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
            <img class="brand-mark" src="{root}crimconsortium-logo.png?v=3" alt="CrimConsortium" width="36" height="36" />
          </a>
          <div class="brand-text">
            <a class="brand-title brand-title-link" href="{root}index.html">{esc(site['name'])}</a>
          </div>
        </div>
        <div class="header-actions">
          <nav class="site-nav" aria-label="Site">
            {nav("search.html", "Search", "search")}
            {nav("about.html", "About the data", "about")}
            {nav("sampling.html", "Sampling", "sampling")}
          </nav>
          <button class="icon-btn" type="button" data-theme-toggle aria-label="Toggle color scheme" title="Toggle light or dark"></button>
        </div>
      </header>

      <main id="main">
{body}
      </main>

      <footer class="site-footer">
        <div class="footer-note">
          Compiled from published news reports found through Google News and Bing News searches, refreshed daily
          (<a href="{root}sampling.html">how cases are sampled</a>).
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

def home(pairs, cfg, updated, n_reports, waiting=0) -> str:
    site = cfg["site"]
    n = int(site.get("homepage_count", 10))
    latest = [v for _, v in pairs[:n]]
    items = "\n".join(incident_item(v) for v in latest)
    total = len(pairs)
    mail = esc(site["contact_email"])
    waiting_note = (f", and {waiting:,} more candidate {'case is' if waiting == 1 else 'cases are'} waiting to be coded"
                    if waiting else "")
    if not latest:
        items = '          <li class="incident"><p class="incident-summary">The first cases are being coded and will appear here shortly.</p></li>'
    body = f"""        <section class="hero">
          <div class="hero-eyebrow">A dataset provided by <a href="https://crimconsortium.com" target="_blank" rel="noopener">CrimConsortium</a> · Last updated {ex.nice_date(updated)}</div>
          <h1 class="hero-title">Self-driving incidents: <span class="hero-line"><em>claimed, questioned, confirmed</em>.</span></h1>
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
        </section>

        <section aria-labelledby="latest-title">
          <div class="section-head"><h2 class="section-title" id="latest-title">Latest incidents</h2></div>
          <p class="section-note section-note-wide">
            The {min(n, total) if total else n} most recent, newest first. Each summary is the publisher's own words.
            Labels record what coverage says, not what has been established, and the coding behind
            them is machine-drafted and not yet reviewed. This is not a complete list{waiting_note}:
            <a class="text-link" href="sampling.html">how cases are found, and why some are old</a>.
          </p>
          <ol class="incident-list">
{items}
          </ol>
        </section>"""
    first = min((v["first"] for _, v in pairs), default=updated)
    ld = [dataset_ld(cfg, updated, total, first), ORG,
          {"@type": "WebSite", "@id": site["url"] + "#website", "url": site["url"], "name": site["name"],
           "publisher": {"@id": ORG["@id"]},
           "potentialAction": {"@type": "SearchAction", "target": site["url"] + "search.html?q={search_term_string}",
                               "query-input": "required name=search_term_string"}}]
    return shell(cfg, path="", current="home", jsonld=ld, body=body,
                 title=f"{site['name']}: Open Data on Tesla Autopilot and FSD incidents",
                 description=("Open dataset of crashes, near misses, police stops and court cases in which Tesla "
                              "Autopilot, Full Self-Driving or another automated-driving feature is claimed, questioned or confirmed. "
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
    joined = ""
    if v.get("merged"):
        ids = v["merged"]
        ids = [f'<span class="nowrap">{i}</span>' for i in ids]
        names = ", ".join(ids[:-1]) + (" and " if len(ids) > 1 else "") + ids[-1]
        joined = (f'\n          <p class="case-meta case-joined">Includes the reports formerly filed as {names}, which '
                  f'described the same event. {"Those IDs are" if len(ids) > 1 else "That ID is"} retired; see '
                  f'<a class="text-link" href="{root}data/retired_ids.csv" download>retired_ids.csv</a>.</p>')
    body = f"""        <nav class="crumbs" aria-label="Breadcrumb"><a href="{root}index.html">Latest incidents</a> / <span class="case-id">{v["id"]}</span></nav>
        <header class="case-head">
          <div class="incident-eyebrow"><span class="incident-lead">{esc(v["lead"])}</span><span class="incident-date">{esc(v["date_label"])}</span></div>
          <h1>{esc(v["title"])}</h1>
          <p class="case-meta">Headline from {esc(v["publisher"])} · {n} report{"s" if n != 1 else ""} · first reported {ex.nice_date(v["first"])} · record updated {ex.nice_date(case["updated"][:10])}</p>{joined}
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
    limit = int(cfg["coder"].get("max_sources_per_case", 5))
    since = str(cfg.get("backfill_from") or cfg.get("collection_started") or "")
    since_txt = f", in news published since {ex.nice_date(since)}" if since else ""
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
          <p>The searches, the rules for keeping a report, the time period covered and the known gaps are set out in full on the <a href="sampling.html">sampling page</a>.</p>

          <h2>How cases are coded</h2>
          <p>A language model reads up to {limit} of the reports attached to a case: those with the most text, always including the newest. It reads the article text where the publisher allows it, otherwise the headline and summary; <code>sources.csv</code> marks which reports were read and how. From these it drafts the coded variables, a short neutral narrative, and a list of who said what. Three rules limit what it can assert:</p>
          <ul>
            <li>It may use only the reports it was given for that case.</li>
            <li>Every coded value must come with a quotation, and the program keeps the value only if that quotation is found word for word in the report. Values that fail are removed and counted on the case page.</li>
            <li>A mention of a feature is never treated as evidence that it was in use. The variable <code>engagement_status</code> separates what an official source or the maker's own data states from what a driver, lawyer or witness claims.</li>
          </ul>
          <p>Every record is marked &ldquo;{esc(cb.REVIEW_STATUS)}&rdquo; until a person has checked it. Summaries shown on the homepage are each publisher's own words, not ours.</p>

          <h2>What it cannot tell you</h2>
          <ul>
            <li><strong>It is not a count of all incidents.</strong> It holds only incidents that reached published news in English and that our searches found{since_txt}. Many incidents are never reported.</li>
            <li><strong>Counts are not rates.</strong> Nothing here says how often these features are used without incident, so the data cannot show whether they are safer or less safe than a human driver.</li>
            <li><strong>It does not establish fault or cause.</strong> It records what coverage reports and who says so.</li>
            <li><strong>Machine coding makes mistakes.</strong> Dates, places and counts can be wrong, and two cases may turn out to be the same event. Check the linked sources before relying on a record.</li>
            <li><strong>Case IDs are permanent, and a few are retired.</strong> When the reports show that two cases are one event, they are joined under the lower ID and that case is coded again from the combined reports. Joining is a separate, recorded step with a written reason; the daily program never joins published cases on its own. The other ID is retired: it is never reused, its page stays in place and points to the case that holds its reports, and it is listed with the reason in <a href="data/retired_ids.csv" download>retired_ids.csv</a>. Cases that only look alike are left separate. The joins made so far were worked out with an AI assistant by comparing the reports and, like the coding, have not yet been checked by a person.</li>
            <li><strong>Coverage changes.</strong> Early reports are often revised. A case reflects the reports attached to it on the date shown.</li>
          </ul>

          <h2>Privacy</h2>
          <p>Coded fields, narratives and claims describe people by role (&ldquo;the driver&rdquo;, &ldquo;a passenger&rdquo;) and do not name private individuals. Names may still appear in publishers' headlines and in the linked reports. This site and the download hold links and short quotations, not copies of articles. So that the coding can be checked, we keep the text of the reports we were able to read in a private archive; it is not part of the dataset and is not redistributed. To ask for a change, email <a href="mailto:{mail}">{mail}</a>.</p>

          <h2>Download, licence and citation</h2>
          <p><a href="data/self-driving-incidents.zip" download>Download everything as one .zip</a>, or take single files: <a href="data/cases.csv" download>cases.csv</a>, <a href="data/evidence.csv" download>evidence.csv</a>, <a href="data/claims.csv" download>claims.csv</a>, <a href="data/sources.csv" download>sources.csv</a>, <a href="data/screened_out.csv" download>screened_out.csv</a>, <a href="data/retired_ids.csv" download>retired_ids.csv</a>, <a href="data/cases.json" download>cases.json</a>, <a href="data/codebook.json" download>codebook.json</a>.</p>
          <p>The data are free to reuse under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>. The code that builds them is on <a href="{esc(site['repo'])}" target="_blank" rel="noopener">GitHub</a>, where every change to the data is recorded.</p>
          <p>Cite as: CrimConsortium. <em>{esc(site['name'])}</em> [dataset]. {esc(site['url'])} (data as of {ex.nice_date(updated)}; codebook version {cb.VERSION}).</p>

          <h2 id="codebook">Codebook, version {cb.VERSION}</h2>
          <p>{len(cb.VARIABLES)} coded variables. Select one to see its definition and allowed values. A blank value means the reports read did not state it.</p>
        </div>
        <div class="codebook">
{codebook_html()}
        </div>"""
    ld = [{"@type": "WebPage", "@id": site["url"] + "about.html", "url": site["url"] + "about.html",
           "name": f"About the data | {site['name']}", "dateModified": updated,
           "isPartOf": {"@id": site["url"] + "#website"}, "about": {"@id": site["url"] + "#dataset"},
           "publisher": {"@id": ORG["@id"]}}, ORG]
    return shell(cfg, path="about.html", current="about", body=body, jsonld=ld,
                 title=f"About the data and codebook | {site['name']}",
                 description="How the Self-Driving Incidents Explorer finds and codes cases, what the data can and "
                             "cannot show, the full codebook, licence and citation.")


# --------------------------------------------------------------------------- sampling page

def sampling_stats(store: dict, cfg: dict) -> dict:
    from collections import Counter
    """Counts shown on the sampling page, taken from the working record on every rebuild."""
    cases = store["cases"]
    days = sorted(s["published"][:10] for c in cases for s in c["sources"] if s.get("published"))
    started = str(cfg.get("collection_started") or min((c["added"][:10] for c in cases if c.get("added")), default=""))
    return {
        "reports": sum(len(c["sources"]) for c in cases), "cases": len(cases),
        "published": sum(c["status"] == "published" for c in cases),
        "excluded": sum(c["status"] == "excluded" for c in cases),
        "pending": sum(c["status"] == "pending" for c in cases),
        "retired": len(store.get("retired", [])),
        "reports_published": sum(len(c["sources"]) for c in cases if c["status"] == "published"),
        "reports_read": sum(
            sum(1 for s in c["sources"] if s["url"] in {r["url"] for r in (c.get("coding") or {}).get("sources_read", [])})
            for c in cases if c["status"] == "published"),
        "first_report": days[0] if days else "", "last_report": days[-1] if days else "",
        "started": started, "backfill": str(cfg.get("backfill_from") or ""),
        "live_from": _days_before(started, int(cfg.get("lookback_days", 7))) if started else "",
        "by_month": sorted(Counter(d[:7] for d in days).items()),
    }


def _days_before(iso: str, n: int) -> str:
    from datetime import date, timedelta
    return (date.fromisoformat(iso) - timedelta(days=n)).isoformat()


def sampling_page(cfg, stats, updated) -> str:
    site = cfg["site"]
    mail = esc(site["contact_email"])
    repo = esc(site["repo"])
    look = int(cfg.get("lookback_days", 7))
    sim = int(cfg.get("similarity_threshold", 75))
    need = int(cfg.get("merge_min_shared_words", 4))
    kw = cfg["keywords"]
    limit = int(cfg["coder"].get("max_sources_per_case", 5))
    makers = ", ".join(m["name"] for m in cfg["makers"])
    google = "".join(f"<li><code>{esc(q)}</code></li>" for m in cfg["makers"] for q in m.get("queries", []))
    bing = "".join(f"<li><code>{esc(q)}</code></li>" for m in cfg["makers"] for q in m.get("bing_queries", []))
    terms = lambda words: ", ".join(esc(w) for w in words)
    plural = lambda n, one, many: f"{n:,} {one if n == 1 else many}"
    live_from, back = stats["live_from"], stats["backfill"]
    n_gone = stats.get("retired", 0)
    joined_note = (f" Published cases that the reports show to be one event are joined under the lower ID in a separate, "
                   f"recorded step, never by the daily program; {n_gone} case ID{'s have' if n_gone != 1 else ' has'} "
                   f"been retired this way so far, each listed with the reason in "
                   f"<a href=\"data/retired_ids.csv\" download>retired_ids.csv</a>. Those joins were worked out with an "
                   f"AI assistant by comparing the reports and have not yet been checked by a person." if n_gone else "")
    n_pub, n_read = stats.get("reports_published", 0), stats.get("reports_read", 0)
    shorter = ("Until the waiting cases are coded, the published list will stay much shorter than the list of what has been found."
               if stats["pending"] else
               "Most of what the searches return is not a single identifiable incident, which is why the published list "
               "is much shorter than the list of what has been found.")
    gone_row = (f"<tr><th>Retired case IDs</th><td>{n_gone:,}, duplicates joined into a published case and listed in "
                f"<a href=\"data/retired_ids.csv\" download>retired_ids.csv</a>. Their reports are counted under the "
                f"case that now holds them.</td></tr>" if n_gone else "")
    read_note = (f" So far it has read {n_read:,} of the {n_pub:,} reports attached to published cases; "
                 f"<code>sources.csv</code> marks which." if n_pub else "")
    searched_from = back or live_from
    days_all = stats["by_month"]
    older = sum(n for m, n in days_all if m < searched_from[:7])
    months = "".join(f"<tr><th>{ex.nice_date(m)}</th><td>{n:,}</td></tr>" for m, n in days_all)
    if back:
        when = (f"Collection began on {ex.nice_date(stats['started'])}. Each daily run looks back {look} days. "
                f"On the first day the Google News searches were also repeated one week at a time back to "
                f"{ex.nice_date(back)}, so the dataset draws on news published since then. Nothing earlier has been searched.")
        thin = (f"The weeks before {ex.nice_date(live_from)} were searched after the fact, on Google News only, and return "
                f"whatever it still lists for those weeks. Expect them to be thinner than the period collected live.")
        brief = (f"It is every case found by a fixed set of news searches, in news published since {ex.nice_date(back)}, "
                 f"that has been coded and has passed the screening rules below.")
    else:
        when = (f"Collection began on {ex.nice_date(stats['started'])}. The first run looked back {look} days, and each daily "
                f"run since has done the same. The dataset has not been filled in for earlier months or years, so it holds "
                f"roughly the news of the period since then, not the history of these incidents.")
        thin = "Earlier periods can be searched week by week (see <a href=\"#reproduce\">the last section</a>), but that has not been done yet."
        brief = (f"It is every case that a fixed set of daily news searches has found since {ex.nice_date(stats['started'])} "
                 f"and that passed the screening rules below.")
    backlog = (f" <strong>{stats['pending']:,} candidate cases are still waiting to be coded</strong>, so the published list "
               f"is a small part of what has been found." if stats["pending"] > stats["published"] else "")
    body = f"""        <header class="page-head">
          <h1>Sampling: how cases get into the dataset</h1>
          <p>Where reports come from, which are kept, how they become cases, and what that means for what the data can support.</p>
        </header>
        <div class="prose">
          <p class="notice" style="margin-top: 0"><strong>In brief.</strong> This is not a complete list or a random sample of incidents. {brief}{backlog} It can show what kinds of incidents are reported and how they are handled. It cannot show how often they happen.</p>

          <h2 id="why-few">Why there are few cases, and why some are old</h2>
          <p>{when}</p>
          <p>{thin}</p>
          <p>Finding a report is only the first step. A case appears on the site after it has been coded and screened, and {stats["excluded"]:,} of the {stats["published"] + stats["excluded"]:,} cases coded so far were set aside (see <a href="#numbers">the numbers</a>). {shorter}</p>
          <p>Cases are dated by when the incident happened, not when it was reported, so an old incident appears whenever it is in current news. That happens in two ways:</p>
          <ul>
            <li><strong>New coverage of an old event.</strong> A verdict, an appeal, a settlement or a regulator's report brings an earlier crash back into the news. A crash from 2019 can enter the dataset because of a court filing this month.</li>
            <li><strong>Older articles returned by a search.</strong> One of the two news searches has no date limit and sometimes lists articles that are months or years old. They are kept if they pass the rules. Of the {plural(stats["reports"], "report", "reports")} collected so far, {older:,} {"was" if older == 1 else "were"} published before {ex.nice_date(searched_from[:7])}.</li>
          </ul>
          <p>So a case dated 2023 does not mean coverage of 2023 is complete. It means one incident from 2023 was in the news we searched.</p>

          <h2 id="numbers">The numbers so far</h2>
          <table class="var-table">
            <tr><th>Reports kept</th><td>{stats["reports"]:,}, published between {ex.nice_date(stats["first_report"])} and {ex.nice_date(stats["last_report"])}</td></tr>
            <tr><th>Candidate cases</th><td>{stats["cases"]:,}, after grouping reports about the same event</td></tr>
            <tr><th>Published</th><td>{stats["published"]:,} cases, holding {n_pub:,} of the reports</td></tr>
            <tr><th>Screened out</th><td>{stats["excluded"]:,}, each listed with its reason in <a href="data/screened_out.csv" download>screened_out.csv</a></td></tr>
            <tr><th>Waiting to be coded</th><td>{stats["pending"]:,}. These are not shown on the site until they have been coded and screened.</td></tr>
            {gone_row}
          </table>
          <p style="margin-top: var(--space-3)">These figures are recalculated every time the site is rebuilt.</p>
          <details class="month-counts">
            <summary>Reports kept, by month of publication</summary>
            <table class="var-table">{months}</table>
          </details>

          <h2 id="sources">Where reports come from</h2>
          <p>Once a day a program runs the searches below on Google News (United States, English edition) and Bing News. The Google searches are limited to the last {look} days. Bing offers no date limit, so it returns whatever it currently lists. No other source is searched: not police or court records, regulators' databases, social media or reader submissions.</p>
          <h3>Google News searches</h3>
          <ul class="query-list">{google}</ul>
          <h3>Bing News searches</h3>
          <ul class="query-list">{bing}</ul>
          <p>Makers covered: {esc(makers)}. Each search returns only the results the service chooses to list, in an order it does not explain, and the same search can return different results on different days.</p>

          <h2 id="kept">Which reports are kept</h2>
          <p>A report is kept when its headline (or, for Bing, the short description supplied with it) names an automated-driving feature <em>and</em> its headline points to something that happened. Headlines with a finance or product term are dropped first. The word lists are:</p>
          <ul>
            <li><strong>Feature terms:</strong> {terms(kw["automation"])}.</li>
            <li><strong>Event terms:</strong> {terms(kw["incident"])}.</li>
            <li><strong>Dropped if the headline has:</strong> {terms(kw["exclude"])}.</li>
          </ul>
          <p>The rule is applied to headlines, not article text. An article whose headline says only &ldquo;Tesla crash&rdquo; is missed even if the article discusses Autopilot.</p>

          <h2 id="cases">How reports become cases</h2>
          <p>The unit is the incident, not the article. Reports are joined into one case by rule, and the rules are cautious, so they are more likely to leave one event as two cases than to join two events:</p>
          <ul>
            <li>The same link, or the same publisher and headline, is counted once.</li>
            <li>Two reports are compared only if they were published within {cluster.WINDOW_DAYS} days of each other and do not name different U.S. states.</li>
            <li>They are treated as the same event when their headlines are nearly identical (90% alike), or at least {sim}% alike and share two distinctive words, or share three distinctive words with one headline largely contained in the other. Similar wording alone is not enough: &ldquo;Tesla in self-driving mode involved in crash&rdquo; fits many events.</li>
            <li>Reports within {cluster.CLOSE_DAYS} days of each other are also treated as the same event when their headlines and summary lines share at least {need} specific words (places, road numbers, charges).</li>
            <li>A report joins a case when it matches any report already in that case. Dates are compared report to report, so a case with months of coverage does not pull in unrelated later news.</li>
            <li>At coding time the model is shown earlier published cases and may say a new one is the same incident, in which case the reports are joined. The cases shown are those that share specific headline words, those whose coded city appears in the reports being read, and those with coverage published within three days of the new reports.</li>
          </ul>

          <h2 id="screening">Which cases are published</h2>
          <p>A case is published only when the coding step finds all of the following in the reports. Otherwise it is set aside and listed with the reason.</p>
          <ul>
            <li><strong>One identifiable incident.</strong> Statistics, policy stories, explainers, product news and opinion pieces are set aside.</li>
            <li><strong>Not a round-up.</strong> An article covering several separate incidents is set aside rather than split into cases, because its details usually cannot be tied to one event.</li>
            <li><strong>An automated-driving feature is claimed, questioned or confirmed to be involved.</strong> A crash in which no report raises the feature is set aside.</li>
            <li><strong>A covered maker.</strong> Incidents involving another maker's vehicle are set aside for now.</li>
          </ul>
          <p>The coding step reads up to {limit} reports per case: those with the most text, always including the newest.{read_note} Where a publisher blocks automated reading, only the headline and summary are available, and the variable <code>text_basis</code> records which was used. A published case is never withdrawn automatically; it is recoded when new reports are attached to it.</p>

          <h2 id="limits">Known gaps and biases</h2>
          <ul>
            <li><strong>News decides what is here.</strong> Deaths, arrests, lawsuits and anything on video are far more likely to be reported than minor events, so serious and unusual incidents are over-represented.</li>
            <li><strong>English, and mostly the United States.</strong> The searches use English terms and a U.S. news edition.</li>
            <li><strong>Search services are a filter we do not control.</strong> Their ranking, limits and removals are not documented, so the collection cannot be exactly repeated.</li>
            <li><strong>Time coverage is uneven.</strong> Fullest for news published from {ex.nice_date(live_from)} onward, which was collected live from both search services. {("News from " + ex.nice_date(back) + " to then was searched afterwards on Google News only and is thinner. Anything earlier is accidental.") if back else "Sparse and accidental before."}</li>
            <li><strong>Headline wording matters.</strong> Incidents reported without a feature term in the headline are missed; incidents where the feature is the story are favoured.</li>
            <li><strong>Round-ups are lost.</strong> An incident reported only inside a round-up does not become a case.</li>
            <li><strong>Duplicates and wrong joins are possible.</strong> Two cases may be one event, and rarely one case may mix two. The joining rules were tightened on November 22, 2026 after a test showed that the earlier rules let a long-running case absorb unrelated reports; nothing from that test was published. On the same day the first automated coding batch published 32 cases, several of which duplicated one another because the model was shown too few earlier cases to compare against; those 32 were returned to the waiting list within the hour, the comparison list was widened, and they were coded again.{joined_note}</li>
            <li><strong>Coding has changed hands.</strong> Each record names its coder in the <code>coder</code> column; the first cases were drafted by a different model from the one the daily job is set to use. None has been reviewed by a person yet.</li>
            <li><strong>No denominator.</strong> Nothing here measures how much these features are used, so counts cannot be turned into rates or risks.</li>
          </ul>

          <h2 id="reproduce">Check it or change it</h2>
          <p>Everything on this page is read from the settings and code that run the collection, which are public:</p>
          <ul>
            <li><a href="{repo}/blob/main/config.yaml" target="_blank" rel="noopener">config.yaml</a>: the searches, word lists and thresholds.</li>
            <li><a href="{repo}/blob/main/pipeline/collect.py" target="_blank" rel="noopener">collect.py</a> and <a href="{repo}/blob/main/pipeline/cluster.py" target="_blank" rel="noopener">cluster.py</a>: how reports are fetched, kept and grouped.</li>
            <li><a href="{repo}/blob/main/pipeline/coder.py" target="_blank" rel="noopener">coder.py</a>: the screening and quotation checks.</li>
            <li><a href="{repo}/commits/main" target="_blank" rel="noopener">Change history</a>: every daily refresh, with its counts.</li>
          </ul>
          <p>Earlier periods are searched with <code>python -m pipeline.run --backfill 2026-01-01</code>, which repeats the Google searches one week at a time back to the date given. Results for past weeks are whatever Google News still lists, so a search of the past will be thinner than live collection.</p>
          <p>See also <a href="about.html">About the data</a> for how cases are coded and the codebook. Suggestions for other sources or search terms are welcome at <a href="mailto:{mail}">{mail}</a>.</p>
        </div>"""
    ld = [{"@type": "WebPage", "@id": site["url"] + "sampling.html", "url": site["url"] + "sampling.html",
           "name": f"Sampling | {site['name']}", "dateModified": updated,
           "isPartOf": {"@id": site["url"] + "#website"}, "about": {"@id": site["url"] + "#dataset"},
           "publisher": {"@id": ORG["@id"]}}, ORG]
    return shell(cfg, path="sampling.html", current="sampling", body=body, jsonld=ld,
                 title=f"Sampling: how cases are found and screened | {site['name']}",
                 description="How the Self-Driving Incidents Explorer samples incidents: the news searches used, "
                             "which reports are kept, how cases are screened, time coverage, and known gaps.")


# --------------------------------------------------------------------------- retired case IDs

def retired_page(r: dict, cfg: dict) -> str:
    """What a retired case ID's address shows: where its reports went, when, and why."""
    site = cfg["site"]
    root = "../"
    old, new = r["case_id"], r["merged_into"]
    n = r.get("n_reports")
    moved = f" Its {n} report{'s' if n != 1 else ''} moved with it." if n else ""
    body = f"""        <nav class="crumbs" aria-label="Breadcrumb"><a href="{root}index.html">Latest incidents</a> / <span class="case-id">{old}</span></nav>
        <header class="case-head">
          <div class="incident-eyebrow"><span class="incident-lead">Retired case ID</span><span class="incident-date">Retired {ex.nice_date(r["retired_on"])}</span></div>
          <h1><span class="nowrap">{old}</span> is now part of <span class="nowrap">{new}</span></h1>
          <p class="case-meta">Formerly: {esc(r["headline"])} ({esc(r["headline_publisher"])})</p>
        </header>
        <section class="case-section">
          <div class="prose">
            <p>This case described the same event as <a class="nowrap" href="{new}.html">{new}</a>, so the two were joined on {ex.nice_date(r["retired_on"])}.{moved} The ID <span class="nowrap">{old}</span> is retired and will not be given to another case.</p>
            <p><strong>Why they were joined:</strong> {esc(r["reason"])}</p>
            <p>If you cited <span class="nowrap">{old}</span>, cite <span class="nowrap">{new}</span> instead. Every retired ID is listed in <a href="{root}data/retired_ids.csv" download>retired_ids.csv</a>.</p>
          </div>
        </section>
        <div class="case-actions">
          <a class="btn-primary" href="{new}.html">Go to {new}</a>
          <a class="btn-secondary" href="{root}search.html">Search all cases</a>
        </div>"""
    return shell(cfg, path=f"cases/{old}.html", root=root, body=body, canonical=site["url"] + f"cases/{new}.html",
                 title=f"{old} is now part of {new} | {site['name']}",
                 description=f"Case {old} described the same event as {new} and was joined to it on "
                             f"{ex.nice_date(r['retired_on'])}. {old} is a retired case ID.")


# --------------------------------------------------------------------------- write

def write_pages(pairs, cfg, updated, n_reports, stats=None, retired=None) -> None:
    site = cfg["site"]
    total = len(pairs)
    ex.write_if_changed(ROOT / "index.html", home(pairs, cfg, updated, n_reports, (stats or {}).get("pending", 0)))
    ex.write_if_changed(ROOT / "search.html", search_page(cfg, total))
    ex.write_if_changed(ROOT / "about.html", about_page(cfg, total, updated))
    if stats:
        ex.write_if_changed(ROOT / "sampling.html", sampling_page(cfg, stats, updated))
    for case, v in pairs:
        ex.write_if_changed(ROOT / v["url"], case_page(case, v, cfg))
    for r in retired or []:   # a retired ID keeps its address and points to the surviving case
        ex.write_if_changed(ROOT / "cases" / f"{r['case_id']}.html", retired_page(r, cfg))
    urls = [(site["url"], updated, "daily", "1.0"), (site["url"] + "search.html", updated, "daily", "0.8"),
            (site["url"] + "about.html", updated, "monthly", "0.7")]
    if stats:
        urls.append((site["url"] + "sampling.html", updated, "weekly", "0.7"))
    urls += [(site["url"] + v["url"], c["updated"][:10], "monthly", "0.6") for c, v in pairs]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"  <url><loc>{esc(u)}</loc><lastmod>{d}</lastmod><changefreq>{f}</changefreq><priority>{p}</priority></url>"
            for u, d, f, p in urls]
    ex.write_if_changed(ROOT / "sitemap.xml", "\n".join(xml + ["</urlset>"]) + "\n")
    ex.write_if_changed(ROOT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site['url']}sitemap.xml\n")
