/* Search and filter the full dataset. Data comes from data/site-data.js (window.SDI). */
(function () {
  var D = window.SDI || { cases: [], labels: { system: {}, status: {}, type: {} } };
  var PAGE = 50;
  var state = { q: "", system: {}, status: {}, type: {}, deaths: {}, year: {}, state: "", sort: "new", shown: PAGE };
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  function count(key, value, multi) {
    return D.cases.filter(function (c) {
      return multi ? c.f[key].indexOf(value) !== -1 : String(c.f[key]) === String(value);
    }).length;
  }

  function checkboxes(el, key, options, multi) {
    el.innerHTML = options.map(function (o) {
      var n = count(key, o.value, multi);
      if (!n) return "";
      return '<label class="checkbox-item"><input type="checkbox" data-key="' + key + '" value="' + esc(o.value) + '">' +
        '<span class="checkbox-item-label">' + esc(o.label) + '</span><span class="checkbox-item-count">' + n + "</span></label>";
    }).join("") || '<span class="panel-hint">Nothing coded yet.</span>';
  }

  function buildFilters() {
    var L = D.labels;
    checkboxes($("f-system"), "system", Object.keys(L.system).map(function (k) { return { value: k, label: L.system[k] }; }), true);
    checkboxes($("f-status"), "status", Object.keys(L.status).map(function (k) { return { value: k, label: L.status[k] }; }), false);
    checkboxes($("f-type"), "type", Object.keys(L.type).map(function (k) { return { value: k, label: L.type[k] }; }), false);
    checkboxes($("f-deaths"), "deaths", [{ value: 1, label: "Deaths reported" }], false);
    var years = {};
    D.cases.forEach(function (c) { if (c.f.year) years[c.f.year] = 1; });
    checkboxes($("f-year"), "year", Object.keys(years).sort().reverse().map(function (y) { return { value: y, label: y }; }), false);
    var states = {};
    D.cases.forEach(function (c) { if (c.f.state) states[c.f.state] = (states[c.f.state] || 0) + 1; });
    var names = Object.keys(states).sort(function (a, b) { return states[b] - states[a] || a.localeCompare(b); });
    $("f-state").innerHTML = ['<button type="button" class="dept-item active" data-state=""><span>All places</span><span class="dept-count">' + D.cases.length + "</span></button>"]
      .concat(names.map(function (s) {
        return '<button type="button" class="dept-item" data-state="' + esc(s) + '"><span>' + esc(s) + '</span><span class="dept-count">' + states[s] + "</span></button>";
      })).join("");
  }

  function any(o) { return Object.keys(o).length > 0; }

  function matches(c) {
    if (state.q) {
      var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var i = 0; i < words.length; i++) if (c.q.indexOf(words[i]) === -1) return false;
    }
    if (any(state.system) && !c.f.system.some(function (s) { return state.system[s]; })) return false;
    if (any(state.status) && !state.status[c.f.status]) return false;
    if (any(state.type) && !state.type[c.f.type]) return false;
    if (any(state.deaths) && !c.f.deaths) return false;
    if (any(state.year) && !state.year[c.f.year]) return false;
    if (state.state && c.f.state !== state.state) return false;
    return true;
  }

  function item(c) {
    var tags = c.tags.map(function (t) {
      return '<span class="tag' + (t.kind === "status" ? " tag-status" : "") + '">' + esc(t.label) + "</span>";
    }).join("");
    var src = c.src.map(function (s) {
      return '<a href="' + esc(s.u) + '" target="_blank" rel="noopener">' + esc(s.p) + "</a>";
    }).join(", ") + (c.n > c.src.length ? ", and " + (c.n - c.src.length) + " more" : "");
    var summary = c.summary
      ? '<p class="incident-summary">' + esc(c.summary) + ' <span class="incident-by">(' + esc(c.kind === "publisher" ? c.by : "Machine-drafted summary") + ")</span></p>"
      : "";
    return '<li class="incident"><div class="incident-eyebrow"><span class="incident-lead">' + esc(c.lead) +
      '</span><span class="incident-date">' + esc(c.date) + '</span></div><h3 class="incident-title"><a href="' + esc(c.url) + '">' +
      esc(c.title) + "</a></h3>" + summary + '<div class="incident-tags">' + tags + '</div><div class="incident-foot"><span>Reported by ' +
      src + '</span><a class="incident-more" href="' + esc(c.url) + '" aria-label="Full record for ' + esc(c.id) + '">Full record</a></div></li>';
  }

  function chips() {
    var out = [];
    var L = D.labels;
    function add(label, fn) { out.push({ label: label, fn: fn }); }
    if (state.q) add("\u201c" + state.q + "\u201d", function () { state.q = ""; $("search-input").value = ""; });
    Object.keys(state.system).forEach(function (k) { add(L.system[k], function () { delete state.system[k]; }); });
    Object.keys(state.status).forEach(function (k) { add(L.status[k], function () { delete state.status[k]; }); });
    Object.keys(state.type).forEach(function (k) { add(L.type[k], function () { delete state.type[k]; }); });
    if (any(state.deaths)) add("Deaths reported", function () { state.deaths = {}; });
    Object.keys(state.year).forEach(function (k) { add(k, function () { delete state.year[k]; }); });
    if (state.state) add(state.state, function () { state.state = ""; });
    var el = $("active-filters");
    el.innerHTML = out.map(function (c, i) {
      return '<span class="active-chip">' + esc(c.label) + '<button type="button" data-chip="' + i + '" aria-label="Remove filter ' + esc(c.label) +
        '"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></span>';
    }).join("");
    el.onclick = function (e) {
      var b = e.target.closest("[data-chip]");
      if (!b) return;
      out[+b.getAttribute("data-chip")].fn();
      syncControls();
      render();
    };
    return out.length;
  }

  function syncControls() {
    document.querySelectorAll('.sidebar input[type="checkbox"]').forEach(function (cb) {
      cb.checked = !!state[cb.getAttribute("data-key")][cb.value];
    });
    document.querySelectorAll("#f-state .dept-item").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-state") === state.state);
    });
  }

  function render() {
    var rows = D.cases.filter(matches);
    rows.sort(function (a, b) {
      if (state.sort === "reports") return b.n - a.n || (a.sort < b.sort ? 1 : -1);
      if (state.sort === "old") return a.sort < b.sort ? -1 : a.sort > b.sort ? 1 : 0;
      return a.sort < b.sort ? 1 : a.sort > b.sort ? -1 : 0;
    });
    var active = chips();
    $("results").innerHTML = rows.slice(0, state.shown).map(item).join("");
    $("results-title").textContent = active ? "Matching cases" : "All cases";
    $("results-meta").textContent = rows.length + (rows.length === 1 ? " case" : " cases") +
      (active ? " of " + D.cases.length : "") + (D.updated ? " \u00b7 data as of " + D.updated : "");
    $("empty-state").hidden = rows.length > 0;
    $("results").hidden = rows.length === 0;
    $("more").hidden = rows.length <= state.shown;
    $("more").textContent = "Show " + Math.min(PAGE, rows.length - state.shown) + " more";
    try {
      var url = location.pathname + (state.q ? "?q=" + encodeURIComponent(state.q) : "");
      history.replaceState(null, "", url);
    } catch (e) { /* sandboxed previews may refuse; the page still works */ }
  }

  function init() {
    var q = "";
    try { q = new URLSearchParams(location.search).get("q") || ""; } catch (e) {}
    state.q = q.trim();
    $("search-input").value = state.q;
    buildFilters();
    var timer;
    $("search-input").addEventListener("input", function (e) {
      clearTimeout(timer);
      timer = setTimeout(function () { state.q = e.target.value.trim(); state.shown = PAGE; render(); }, 120);
    });
    document.querySelector(".sidebar").addEventListener("change", function (e) {
      var cb = e.target;
      if (!cb.matches('input[type="checkbox"]')) return;
      var bag = state[cb.getAttribute("data-key")];
      if (cb.checked) bag[cb.value] = true; else delete bag[cb.value];
      state.shown = PAGE;
      render();
    });
    $("f-state").addEventListener("click", function (e) {
      var b = e.target.closest(".dept-item");
      if (!b) return;
      state.state = b.getAttribute("data-state");
      state.shown = PAGE;
      syncControls();
      render();
    });
    $("sort-select").addEventListener("change", function (e) { state.sort = e.target.value; render(); });
    $("more").addEventListener("click", function () { state.shown += PAGE; render(); });
    $("clear-filters").addEventListener("click", function () {
      state.q = ""; state.system = {}; state.status = {}; state.type = {}; state.deaths = {}; state.year = {}; state.state = "";
      state.shown = PAGE; $("search-input").value = "";
      syncControls();
      render();
    });
    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
