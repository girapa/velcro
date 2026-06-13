# Installation

## Requirements

| Requirement | Version |
|-------------|---------|
| Python      | 3.14+   |
| Django      | 6.0+    |

Velcro has no hard dependencies beyond Django itself. Filtering support is the
one optional extra (it pulls in `django-filter`).

## Install the package

```bash
# pip
pip install git+https://github.com/girapa/velcro.git

# uv
uv add git+https://github.com/girapa/velcro.git
```

### With filtering support

The `filter` extra adds `django-filter`, which powers `filterset_fields` and
`filterset_class` (see [Search, ordering, filtering](guides/search-ordering-filtering.md)).
django-filter is only imported when you actually configure filtering, so the
extra is genuinely optional.

```bash
# pip
pip install "velcro[filter] @ git+https://github.com/girapa/velcro.git"

# uv
uv add "velcro[filter] @ git+https://github.com/girapa/velcro.git"
```

## Configure Django

### 1. Add `velcro` to `INSTALLED_APPS`

This makes the bundled templates discoverable.

```python
INSTALLED_APPS = [
    # ...
    "velcro",
]
```

### 2. Ensure `APP_DIRS` is enabled

The bundled templates live in velcro's app directory, so the app-directories
template loader must be active.

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        # ...
    }
]
```

### 3. Provide a base template

Velcro's bundled templates `{% extends %}` a base template and fill its
`content` block. By default they extend `base.html`, so your project needs a
`base.html` somewhere on the template path with a `content` block:

```html
<!-- base.html -->
<!doctype html>
<html>
  <body>
    {% block content %}{% endblock content %}
  </body>
</html>
```

To point at a different base template, set `base_template_name`:

```python
class LeadCRUD(CRUDView):
    base_template_name = "crm/base.html"
```

See [Templates](customisations/templates.md) for the full template story.

### Recommended: messages and request context

Velcro flashes success messages via `django.contrib.messages` and the bundled
templates read `request` directly. Both degrade gracefully if absent
(messages are sent with `fail_silently=True`), but for the full experience
enable:

```python
INSTALLED_APPS = [
    # ...
    "django.contrib.messages",
    "velcro",
]

TEMPLATES = [
    {
        # ...
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
```

## Verify

```python
# views.py
from velcro import CRUDView
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]


# urls.py
urlpatterns = [*LeadCRUD.get_urls()]
```

Visit `/lead/` — you should see the list view. Next:
[Quickstart](quickstart.md).