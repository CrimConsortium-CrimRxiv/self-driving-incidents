/* Homepage case grid: one square per case. The page arrives already arranged by engagement
   status; this script adds the "Arrange by" buttons and the case preview. No libraries. */
(function () {
  var root = document.querySelector("[data-case-grid]");
  var configEl = document.getElementById("grid-config");
  if (!root || !configEl) return;
  var dims = JSON.parse(configEl.textContent).dims;
  var rows = root.querySelector(".grid-rows");
  var controls = root.querySelector(".grid-controls");
  var detail = root.querySelector(".grid-detail");
  var cells = Array.prototype.slice.call(rows.querySelectorAll(".cell"));
  var buttons = Array.prototype.slice.call(controls.querySelectorAll(".grid-btn"));
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  /* ---- rearranging ---- */
  function arrange(key) {
    var dim = dims.filter(function (d) { return d.key === key; })[0];
    if (!dim) return;
    // Where each square is drawn right now, including one that is still moving.
    var from = cells.map(function (c) { return c.getBoundingClientRect(); });
    [rows].concat(cells).forEach(function (c) {
      if (c.getAnimations) c.getAnimations().forEach(function (a) { a.cancel(); });
    });
    var height = rows.offsetHeight;

    var frag = document.createDocumentFragment();
    dim.groups.forEach(function (g) {
      var members = cells.filter(function (c) { return (c.getAttribute("data-" + key) || "") === g[0]; });
      if (!members.length) return;
      var row = el("div", "grid-row");
      row.setAttribute("role", "group");
      row.setAttribute("aria-label", g[1] + ": " + members.length);
      var label = el("div", "grid-label");
      label.appendChild(el("span", "grid-name", g[1]));
      label.appendChild(el("span", "grid-count", String(members.length)));
      var box = el("div", "grid-cells");
      members.forEach(function (c) { box.appendChild(c); });
      row.appendChild(label);
      row.appendChild(box);
      frag.appendChild(row);
    });
    rows.textContent = "";
    rows.appendChild(frag);
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-dim") === key ? "true" : "false"); });

    if (still || !cells[0].animate) return;
    var newHeight = rows.offsetHeight;
    if (newHeight !== height) {
      rows.style.overflow = "hidden";
      var grow = rows.animate([{ height: height + "px" }, { height: newHeight + "px" }],
                              { duration: 420, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
      grow.onfinish = grow.oncancel = function () { rows.style.overflow = ""; };
    }
    cells.forEach(function (c, i) {
      var to = c.getBoundingClientRect();
      var dx = from[i].left - to.left, dy = from[i].top - to.top;
      if (!dx && !dy) return;
      c.animate([{ transform: "translate(" + dx + "px," + dy + "px)" }, { transform: "none" }],
                { duration: 520, delay: Math.min(i * 3, 160), easing: "cubic-bezier(0.2, 0.8, 0.2, 1)", fill: "backwards" });
    });
    var labels = rows.querySelectorAll(".grid-label");
    Array.prototype.forEach.call(labels, function (l) {
      l.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 360, easing: "ease-out" });
    });
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.getAttribute("aria-pressed") !== "true") arrange(b.getAttribute("data-dim"));
    });
  });
  controls.hidden = false;

  /* ---- previewing a case ---- */
  var current = null, armed = null, touch = false;

  function show(c) {
    if (current === c) return;
    if (current) current.classList.remove("is-on");
    current = c;
    c.classList.add("is-on");
    var d = c.dataset;
    var meta = el("p", "grid-detail-meta");
    if (d.lead) meta.appendChild(el("span", "incident-lead", d.lead));
    meta.appendChild(el("span", "incident-date", d.date));
    var title = el("p", "grid-detail-title");
    var link = el("a", "", d.title);
    link.href = c.getAttribute("href");
    title.appendChild(link);
    var foot = el("p", "grid-detail-foot");
    foot.appendChild(el("span", "tag tag-status", d.badge));
    var more = el("a", "incident-more", "Full record");
    more.href = c.getAttribute("href");
    more.setAttribute("aria-label", "Full record for " + d.id);
    foot.appendChild(more);
    foot.appendChild(el("span", "case-id", d.id));
    detail.textContent = "";
    detail.classList.add("has-case");
    detail.appendChild(meta);
    detail.appendChild(title);
    detail.appendChild(foot);
  }

  // With a mouse or keyboard a square is a plain link. On a touch screen the first tap shows the
  // case below the grid and the second tap (or "Full record") opens it.
  root.addEventListener("pointerdown", function (e) {
    touch = e.pointerType === "touch" || e.pointerType === "pen";
    armed = current;
  }, true);
  cells.forEach(function (c) {
    c.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse") show(c); });
    c.addEventListener("focus", function () { show(c); });
    c.addEventListener("click", function (e) {
      if (touch && armed !== c) { e.preventDefault(); show(c); }
    });
  });
})();
