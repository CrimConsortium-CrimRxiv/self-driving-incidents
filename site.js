/* Light/dark toggle, shared by every page. */
(function () {
  var SUN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/></svg>';
  var MOON = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  var btn = document.querySelector("[data-theme-toggle]");
  if (!btn) return;
  function apply(t, save) {
    document.documentElement.setAttribute("data-theme", t);
    btn.innerHTML = t === "dark" ? SUN : MOON;
    btn.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    if (save) { try { localStorage.setItem("sdi-theme", t); } catch (e) {} }
  }
  apply(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light", false);
  btn.addEventListener("click", function () {
    apply(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
  });
})();
