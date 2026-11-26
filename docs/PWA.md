# PesaWise as an installable app (PWA)

PesaWise can be installed on a phone or laptop from the browser, opens full screen with its own icon, and needs **no app store**.
It is the same website and the same codebase.

## What was added
| Piece | File | Purpose |
|---|---|---|
| Web manifest | `core/pwa.py` (`/manifest.webmanifest`) | Name, colours, icons, start page and three app shortcuts |
| Service worker | `templates/pwa/sw.js` (`/sw.js`) | Caches only static files and an offline page |
| Offline page | `templates/pwa/offline.html` (`/offline/`) | Friendly message when there is no connection |
| Install button + registration | `static/js/pwa.js` | Registers the worker; shows **Install app** when the browser allows it |
| Icons | `static/pwa/*.png`, `tools/make_icons.py` | 192, 512, maskable 512, Apple touch icon, favicon |

## Privacy design (important for a finance app)
The service worker **never stores pages, data, exports or anything personal**. It caches only:
1. the app's own static files (CSS, JavaScript, icons), refreshed in the background, and
2. one generic offline page.

Pages always come from the server, so signing out on a shared phone leaves nothing behind. Form submissions are never intercepted.
Downloads (PDF/CSV) are never cached. Tests run the real worker in Node and check each of these rules, and deliberately breaking the
worker makes them fail.

## How to install
- **Android (Chrome):** tap **Install app** in the top bar (or menu, then *Install app*).
- **iPhone (Safari):** Share, then **Add to Home Screen**.
- **Laptop (Chrome/Edge):** the install icon in the address bar.

Requires HTTPS, which the Render deployment provides.

## Check it in the browser
Chrome DevTools, *Application* tab: **Manifest** (installability and icons), **Service Workers** (status, and tick *Offline* to test the
offline page).

## Limits (deliberate)
- Online only. Your records are not available offline, because they are never stored on the device. Offline entry would need
  conflict handling and syncing, which is a separate feature.
- It cannot read SMS. Use paste import, or share a message to the app.
- Not a Play Store or App Store listing. An Android listing is possible later by wrapping this PWA (Trusted Web Activity).

## Maintenance
- Change `PWA_VERSION` in `core/pwa.py` to make every installed copy drop its old cached files.
- After editing the icon design, run `python tools/make_icons.py`.

## Dark mode
Pick **Light**, **Dark** or **Device default** from the theme menu in the top bar (top-right on the login pages), or from the
**Appearance** card on the Profile page. The current choice is ticked.
- The choice is stored in the browser (`localStorage`), never on the server. If storage is blocked, the choice still applies for the visit.
- "Device default" follows the phone or computer setting, including live changes such as night mode.
- A tiny inline script in `<head>` applies the saved theme before the page paints, so there is no white flash.
- Colours are CSS variables (`static/css/style.css`); Bootstrap's `data-bs-theme` handles its own components.
- Charts redraw with theme-appropriate colours when the theme changes.
- `core/test_theme.py` checks WCAG AA contrast for every colour pair in both themes and runs the real theme script in Node.

## Updates reach every device (cache-busting)
- Our own CSS and JavaScript are linked with `{% asset %}`, which adds a hash of the file's contents (`style.css?v=3fa9c1e2`). When a file
  changes its URL changes, so a browser can never keep using an old copy.
- The service worker fetches `/static/` files from the network first and uses its cache only when offline, and it deletes older copies of a
  file when a newer one arrives. (An earlier version served the cache first, which could pair new HTML with old JavaScript.)
- `PWA_VERSION` in `core/pwa.py` can still be bumped to force every installed copy to drop its cache.
