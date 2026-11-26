// Light / Dark / Device-default theme.  The choice is stored on this device only (localStorage), never sent to the server.
// The tiny inline script in <head> (templates/base.html) applies the saved theme before the page paints, so there is no flash.
// Anything with data-theme-choice="light|dark|system" selects a theme when clicked; the active one is highlighted.
(function (root) {
  var KEY = "pw-theme";
  var CHOICES = ["light", "dark", "system"];

  function resolve(choice, prefersDark) {             // -> "light" | "dark"
    return choice === "dark" || (choice !== "light" && !!prefersDark) ? "dark" : "light";
  }
  function isChoice(v) { return CHOICES.indexOf(v) > -1; }
  function read(storage) {                            // safe even if storage is blocked (private mode)
    try { var v = storage.getItem(KEY); return isChoice(v) ? v : "system"; } catch (e) { return "system"; }
  }
  function write(storage, value) { try { storage.setItem(KEY, value); } catch (e) { /* ignore */ } }

  var api = { KEY: KEY, CHOICES: CHOICES, resolve: resolve, isChoice: isChoice, read: read, write: write };
  root.PesaTheme = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (!root.document || !root.document.documentElement) return;

  var doc = root.document;
  var media = root.matchMedia ? root.matchMedia("(prefers-color-scheme: dark)") : null;
  var ICONS = { system: "bi-circle-half", light: "bi-sun", dark: "bi-moon-stars" };
  var NAMES = { system: "Device default", light: "Light", dark: "Dark" };
  var memory = null;                                  // keeps the choice for this visit even if storage is blocked

  function current() { return memory || read(root.localStorage); }

  function apply() {
    var choice = current();
    var theme = resolve(choice, media && media.matches);
    doc.documentElement.setAttribute("data-bs-theme", theme);
    doc.querySelectorAll("[data-theme-choice]").forEach(function (el) {
      var on = el.getAttribute("data-theme-choice") === choice;
      el.classList.toggle("active", on);
      el.setAttribute(el.getAttribute("role") === "menuitemradio" ? "aria-checked" : "aria-pressed", on ? "true" : "false");
    });
    doc.querySelectorAll("[data-theme-current]").forEach(function (btn) {
      var icon = btn.querySelector("i"), label = btn.querySelector(".theme-label");
      if (icon) icon.className = "bi " + ICONS[choice];
      if (label) label.textContent = NAMES[choice];
      btn.setAttribute("aria-label", "Theme: " + NAMES[choice] + ". Click to choose another.");
    });
    doc.dispatchEvent(new root.CustomEvent("themechange", { detail: { theme: theme, choice: choice } }));
  }

  doc.addEventListener("click", function (event) {
    var el = event.target && event.target.closest ? event.target.closest("[data-theme-choice]") : null;
    if (!el) return;
    var value = el.getAttribute("data-theme-choice");
    if (!isChoice(value)) return;                     // ignore anything unexpected
    memory = value;
    write(root.localStorage, value);
    apply();
  });
  if (media && media.addEventListener) {
    media.addEventListener("change", function () { if (current() === "system") apply(); });
  }
  apply();
})(typeof window !== "undefined" ? window : globalThis);
