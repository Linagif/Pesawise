// Runs static/js/theme.js and the inline <head> script against a fake browser; prints results as JSON.
// Usage: node theme_harness.js theme.js early.js
const fs = require("fs");
const vm = require("vm");
const [themeSrc, earlySrc] = [fs.readFileSync(process.argv[2], "utf8"), fs.readFileSync(process.argv[3], "utf8")];

function storage(initial, broken) {
  const data = new Map(initial ? [["pw-theme", initial]] : []);
  return {
    getItem: (k) => { if (broken) throw new Error("blocked"); return data.has(k) ? data.get(k) : null; },
    setItem: (k, v) => { if (broken) throw new Error("blocked"); data.set(k, v); },
    raw: () => data.get("pw-theme") ?? null,
  };
}
function element(attrs) {
  const a = { ...attrs }, classes = new Set();
  return { a, classes,
    getAttribute: (k) => (k in a ? a[k] : null), setAttribute: (k, v) => { a[k] = v; },
    classList: { toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); } },
    closest(sel) { return sel === "[data-theme-choice]" && "data-theme-choice" in a ? this : null; } };
}
function fakeBrowser({ stored = null, prefersDark = false, brokenStorage = false } = {}) {
  const attrs = {}, events = [], icon = { className: "" }, label = { textContent: "" }, curAttrs = {};
  const menu = { light: element({ "data-theme-choice": "light", role: "menuitemradio" }),
                 dark: element({ "data-theme-choice": "dark", role: "menuitemradio" }),
                 system: element({ "data-theme-choice": "system", role: "menuitemradio" }) };
  const profileDark = element({ "data-theme-choice": "dark" });          // a plain button (Appearance card): uses aria-pressed
  const evil = element({ "data-theme-choice": "evil" });
  const current = { querySelector: (s) => (s === "i" ? icon : label), setAttribute: (k, v) => { curAttrs[k] = v; } };
  const media = { matches: prefersDark, _change: null, addEventListener(t, f) { if (t === "change") this._change = f; } };
  let clickHandler = null;
  const documentElement = { setAttribute: (k, v) => { attrs[k] = v; }, getAttribute: (k) => attrs[k] };
  const document = { documentElement,
    querySelectorAll: (s) => (s === "[data-theme-choice]" ? [menu.light, menu.dark, menu.system, profileDark] : s === "[data-theme-current]" ? [current] : []),
    addEventListener: (t, f) => { if (t === "click") clickHandler = f; },
    dispatchEvent: (e) => { events.push(e.type + ":" + e.detail.theme); } };
  class CustomEvent { constructor(type, init) { this.type = type; this.detail = init.detail; } }
  const ls = storage(stored, brokenStorage);
  const win = { document, localStorage: ls, matchMedia: () => media, CustomEvent }; win.window = win;
  const click = (target) => clickHandler({ target });
  const state = () => ({ attr: attrs["data-bs-theme"], stored: ls.raw(), label: label.textContent, icon: icon.className,
    active: Object.entries(menu).filter(([, e]) => e.classes.has("active")).map(([k]) => k),
    checked: Object.entries(menu).filter(([, e]) => e.a["aria-checked"] === "true").map(([k]) => k),
    profileDark: { active: profileDark.classes.has("active"), pressed: profileDark.a["aria-pressed"] }, aria: curAttrs["aria-label"] });
  return { win, attrs, events, media, ls, menu, profileDark, evil, click, state };
}

const out = {};
// 1. pure functions
const pure = {}; vm.runInNewContext(themeSrc, pure);
const T = pure.PesaTheme;
out.resolve = {}; for (const c of ["system", "light", "dark", "weird", null]) for (const p of [false, true]) out.resolve[`${c}|${p}`] = T.resolve(c, p);
out.choices = T.CHOICES;
const bad = storage(null, true);
out.brokenStorage = { read: T.read(bad), writeThrows: (() => { try { T.write(bad, "dark"); return false; } catch (e) { return true; } })() };
out.invalidStored = T.read(storage("purple"));

// 2. picking a theme
let b = fakeBrowser({ prefersDark: true }); vm.runInNewContext(themeSrc, b.win);
out.initial = { ...b.state(), events: b.events.slice() };
b.click(b.menu.light);  out.pickLight = b.state();
b.click(b.menu.dark);   out.pickDark = b.state();
b.click(b.menu.system); out.pickSystem = b.state();                       // device is dark in this scenario
b.click(b.menu.light);  b.click(b.profileDark); out.profileButton = b.state();   // the Appearance card works too
const before = b.state(); b.click(b.evil); b.click({ closest: () => null }); b.click(undefined);
out.ignoresBadClicks = JSON.stringify(before) === JSON.stringify(b.state());
out.eventsAfterPicks = b.events.slice(-2);

// 3. device changes and saved choices
b = fakeBrowser({ stored: "system", prefersDark: false }); vm.runInNewContext(themeSrc, b.win);
b.media.matches = true; b.media._change(); out.systemFollowsDevice = b.state().attr;
b = fakeBrowser({ stored: "light", prefersDark: false }); vm.runInNewContext(themeSrc, b.win);
b.media.matches = true; b.media._change(); out.lightIgnoresDevice = b.state().attr;
b = fakeBrowser({ stored: "dark", prefersDark: false }); vm.runInNewContext(themeSrc, b.win);
out.savedDarkRestored = b.state();

// 4. blocked storage: the choice still works for this visit
b = fakeBrowser({ brokenStorage: true, prefersDark: false }); vm.runInNewContext(themeSrc, b.win);
b.click(b.menu.dark); out.blockedStorageClick = b.state();

// 5. the inline early script must agree with theme.js in every case
out.early = {};
for (const stored of [null, "system", "light", "dark", "weird"]) for (const prefersDark of [false, true]) {
  const e = fakeBrowser({ stored, prefersDark });
  vm.runInNewContext(earlySrc, { document: e.win.document, localStorage: e.win.localStorage, matchMedia: e.win.matchMedia, window: e.win });
  out.early[`${stored}|${prefersDark}`] = { early: e.attrs["data-bs-theme"], full: T.resolve(stored, prefersDark) };
}
const eb = fakeBrowser({ brokenStorage: true, prefersDark: true });
let threw = false; try { vm.runInNewContext(earlySrc, { document: eb.win.document, localStorage: eb.win.localStorage, matchMedia: eb.win.matchMedia, window: eb.win }); } catch (e) { threw = true; }
out.earlyBrokenStorageThrows = threw;
console.log(JSON.stringify(out));
