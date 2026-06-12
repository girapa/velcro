# velcro

**CRUD views for Django.** Heavily inspired by
[Neapolitan](https://github.com/carltongibson/neapolitan) — velcro tries to
bind Django’s common CRUD patterns into a small, reusable API.

Same one-class, one-splat-in-urlpatterns feel — plus permissions, messages,
namespace-aware URLs, search and ordering, custom actions, value
rendering, and first-class HTMX support built on Django 6 template
partials. Zero JavaScript shipped, zero hard dependencies beyond Django.

Requires **Python 3.14+** and **Django 6.0+**.

**N.B. Just testing it out, open to feedback**


## Installation

```bash
# PIP
pip install git+https://github.com/girapa/velcro.git

# with filtering support (django-filter dependency)
pip install "velcro[filter] @ git+https://github.com/girapa/velcro.git"


# UV
uv add git+https://github.com/girapa/velcro.git

# with filtering support (django-filter dependency)
uv add "velcro[filter] @ git+https://github.com/girapa/velcro.git@v0.1.0"
```

### In Django
```
# Add `velcro` to your `INSTALLED_APPS`
INSTALLED_APPS = [
    # ...
    "velcro",
]
```

```
# Check `APP_DIRS=True` in your `TEMPLATES` settings
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        # ...
    }
]
```

```
# You need a `base.html` file in your templates directory, 
# or you can set `base_template_name` to a custom path

class MyView(CRUDView):
    base_template_name = "some/path/to/my/custom_base.html" 
    
# the base tempalte should have a content block somewhere

...
{% block content %}
    ...
{% endblock content %}
...
```

## Quickstart

```python
# views.py
from velcro import CRUDView
from .models import Bookmark

class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]

# urls.py
urlpatterns = [*BookmarkView.get_urls()]
```

That's list, create, detail, update, and delete — routed, named
(`bookmark-list`, `bookmark-detail`, ...), rendered with bundled
framework-agnostic templates, with success messages and sensible
redirects. Your project supplies a `base.html` defining a `content`
block (configurable via `base_template_name`).

## The configuration convention

Every per-action setting resolves through one chain — learn it once:

```
{action}_{name}  ->  {name}  ->  default
```

```python
class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note", "favourite"]   # fallback
    list_fields = ["title", "favourite", "domain"]   # list columns only
    update_form_class = BookmarkUpdateForm           # update only
    create_success_message = "Saved {object}!"       # create only

    def domain(self, obj):                           # callable column
        return obj.url.split("/")[2]
    domain.short_description = "Site"

    def get_list_context_data(self, context):        # per-action hook
        context["intro"] = "All your bookmarks."
        return context
```

List columns render like the admin: choices show their labels, booleans
show ✓/✗, dates and numbers are localized, ForeignKeys link to their
detail page when one is routed, empty values show —.

## Custom actions

Actions are open — a frozen dataclass, not a closed enum:

```python
from velcro import CRUDView, action

class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title"]

    @action(detail=True, methods=["post"], permission="change")
    def archive(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.archive()
        return HttpResponseRedirect(self.reverse("list"))
```

This routes `bookmark/<int:pk>/archive/` named `bookmark-archive`,
405s on GET, and requires `app.change_bookmark` when permissions are on.
Built-ins can be tweaked without redefinition: `UPDATE.using(url_pattern=...)`.

## URLs that behave

- `get_urls()` generates everything; `get_urls(["list", "detail"])` for a
  read-only subset.
- `url_base` (path) and `url_name_prefix` (reverse names) are independent.
- **Namespaces just work**: `self.reverse()` reads the namespace from the
  request, so one view class can be mounted bare, under
  `include(..., namespace="staff")`, or twice under different namespaces.
- Static routes are emitted before lookup routes, so `bookmark/new/` is
  never shadowed by `bookmark/<slug:pk>/`.

## Access control

```python
class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title"]
    login_required = True       # anonymous -> login redirect
    permissions = "model"       # actions map to view/add/change/delete perms
    # or: permissions = {"list": None, "create": "app.add_bookmark"}
```

Failed permission checks raise `PermissionDenied` (403). Object-level
backends (django-guardian, django-rules) are honored automatically on
detail actions via `has_permission(obj=...)` — override it for custom
logic.

## Search, ordering, filtering

```python
class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["title", "url", "status"]
    search_fields = ["title", "^url", "collection__name"]  # ?q=...
    ordering_fields = ["title", "status"]                  # ?ordering=-title
    filterset_fields = ["favourite", "status"]             # needs velcro[filter]
```

Search and ordering have no dependencies; django-filter is optional
(`pip install velcro[filter]`) and only imported when configured.
Pipeline: queryset → filterset → search → ordering → pagination. The
bundled list template renders the search box, filter form, sortable
column headers (▲/▼), and pagination — all composed with
`{% querystring %}` so parameters survive each other.

## HTMX, natively

Pure header/partial protocol — no JS shipped, nothing breaks without
htmx. The bundled templates name their swappable regions with Django 6
core `{% partialdef %}`:

- `HX-Request` on the list → just the `#table` partial, with
  `HX-Push-Url` keeping the URL bar honest.
- `HX-Request` on a form → just the `#form` partial; invalid POSTs
  re-render it with errors in place.
- Successful HTMX mutations → `204` +
  `HX-Trigger: {"bookmarkChanged": {"action": "create", "pk": 7}}`,
  so any list can refresh itself with
  `hx-trigger="bookmarkChanged from:body"`. Set `htmx_events = False`
  for plain redirects, or override `htmx_success_response()` for
  swap-based patterns.

Partial resolution follows the template fallback chain: override a
template without defining partials and partial requests fall back to the
bundled ones.

## Overriding templates

Templates resolve `{template_dir or app_label}/{model}{suffix}.html` →
`velcro/object{suffix}.html`. They're semantic HTML with stable
`velcro-*` classes — style them with any CSS framework or none.

## Testing

```bash
pip install -e .[dev]
pytest
```

## License

MIT.
