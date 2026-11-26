// END-TO-END: loads real rendered pages, runs the page's OWN <script> tags (local files read from disk, in document order)
// in a simulated browser (jsdom), then clicks the real menu. A missing <script> tag therefore makes this fail.
// Usage: node theme_e2e.js pages.json static_dir
const { JSDOM } = require("jsdom");
const fs = require("fs");
const path = require("path");
const pages = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const staticDir = process.argv[3];
const results = {};
for (const [name, html] of Object.entries(pages)) {
  const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://localhost/" });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false, addEventListener() {} });
  const loaded = [], errors = [];
  for (const el of w.document.querySelectorAll("script")) {
    const type = el.getAttribute("type");
    if (type && !/javascript|module/.test(type)) continue;            // data blocks such as application/json are not scripts
    const src = el.getAttribute("src");
    let code;
    if (!src) code = el.textContent;
    else if (src.startsWith("/static/")) { code = fs.readFileSync(path.join(staticDir, src.split("?")[0].replace("/static/", "")), "utf8"); loaded.push(path.basename(src.split("?")[0])); }
    else continue;                                                      // CDN scripts (Bootstrap, Chart.js) are not available offline here
    try { w.eval(code); } catch (e) { errors.push(String(e.message).slice(0, 80)); }
  }
  const q = (s) => [...w.document.querySelectorAll(s)];
  const attr = () => w.document.documentElement.getAttribute("data-bs-theme");
  const r = { loaded, start: attr(), choices: q("[data-theme-choice]").length };
  q('[data-theme-choice="dark"]')[0].click();
  r.afterDark = attr(); r.stored = w.localStorage.getItem("pw-theme");
  r.active = q("[data-theme-choice].active").map((e) => e.getAttribute("data-theme-choice"));
  r.label = (q("[data-theme-current] .theme-label")[0] || {}).textContent;
  q('[data-theme-choice="light"]')[0].click(); r.afterLight = attr();
  q('[data-theme-choice="dark"] i')[0].click(); r.afterIconClick = attr();       // clicking the icon inside a menu item
  q('[data-theme-choice="system"]')[0].click(); r.afterSystem = attr();
  r.errorsOtherThanCharts = errors.filter((e) => !/Chart/.test(e));
  results[name] = r;
}
console.log(JSON.stringify(results));
