"""Progressive Web App support: web manifest, service worker and offline page.

Privacy rule (important for a finance app): the service worker NEVER stores pages or data. It only caches the app's own
static files (CSS, JS, icons) and one generic offline page. Everything personal always comes from the server.
"""
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET

PWA_VERSION = "v1"        # change this to make every installed copy drop its old cached files


@require_GET
def manifest(request):
    icon = lambda name, size, purpose="any": {"src": static(f"pwa/{name}"), "sizes": f"{size}x{size}",   # noqa: E731
                                              "type": "image/png", "purpose": purpose}
    data = {
        "id": "/", "name": "PesaWise: Student Budget Manager", "short_name": "PesaWise",
        "description": "Track income, spending and savings, and get evidence-based money guidance.",
        "start_url": "/?source=pwa", "scope": "/", "display": "standalone", "orientation": "portrait",
        "background_color": "#f2f5f2", "theme_color": "#0b2e24", "lang": "en", "categories": ["finance"],
        "icons": [icon("icon-192.png", 192), icon("icon-512.png", 512), icon("icon-maskable-512.png", 512, "maskable")],
        "shortcuts": [
            {"name": "Add expense", "url": reverse("expenses:add"), "icons": [icon("icon-192.png", 192)]},
            {"name": "Import M-Pesa SMS", "url": reverse("imports:paste"), "icons": [icon("icon-192.png", 192)]},
            {"name": "Financial health", "url": reverse("advisor:tips"), "icons": [icon("icon-192.png", 192)]},
        ],
    }
    response = JsonResponse(data, json_dumps_params={"indent": 2})
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def service_worker(request):
    precache = [reverse("pwa:offline"), static("pwa/icon-192.png"), static("pwa/favicon-32.png")]
    response = render(request, "pwa/sw.js", {"version": PWA_VERSION, "offline_url": reverse("pwa:offline"),
                                              "precache_json": json.dumps(precache)},
                      content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"            # browsers must re-check the worker so updates arrive promptly
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    return render(request, "pwa/offline.html")
