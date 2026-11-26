"""{% asset 'js/theme.js' %} -> /static/js/theme.js?v=<hash of the file's contents>.
Whenever a CSS/JS file changes its URL changes too, so browsers and the service worker can never keep serving an old copy."""
import hashlib
from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=256)
def _digest(path, mtime_ns):
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest()[:8]


@register.simple_tag
def asset(path):
    url = static(path)
    for folder in getattr(settings, "STATICFILES_DIRS", []):
        file = Path(folder) / path
        if file.is_file():
            return f"{url}?v={_digest(str(file), file.stat().st_mtime_ns)}"
    return url
