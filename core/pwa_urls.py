from django.urls import path

from . import pwa

app_name = "pwa"
urlpatterns = [
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("sw.js", pwa.service_worker, name="sw"),          # must live at the site root to control the whole site
    path("offline/", pwa.offline, name="offline"),
]
