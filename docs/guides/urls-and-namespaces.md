# URLs and namespaces

`get_urls()` generates a routed, named URL for every action. Reversing is
namespace-aware, so one view class works mounted bare, under an `include(...,
namespace=...)`, or even twice under different namespaces — with no
configuration.

## What can be customised

| Setting / method   | Default        | Purpose                                          |
|--------------------|----------------|--------------------------------------------------|
| `url_base`         | model name     | First path segment of every generated URL         |
| `url_name_prefix`  | `url_base`     | Prefix of every generated URL *name*               |
| `lookup_field`     | `"pk"`         | Model field used for object lookup                 |
| `lookup_url_kwarg` | `None`         | URL kwarg name (defaults to `lookup_field`)        |
| `path_converter`   | `"int"`        | Path converter for the lookup                      |
| `url_namespace`    | `None`         | Force a namespace; otherwise read from the request |
| `get_urls()`       | all actions    | Generate the patterns                              |
| `reverse()`        | —              | Reverse one of this view's actions                 |
| `maybe_reverse()`  | —              | Like `reverse()` but returns `None` if unrouted    |

## Generating URLs

```python
# crm/urls.py
from .views import LeadCRUD

urlpatterns = [*LeadCRUD.get_urls()]
```

**Outcome** — for `LeadCRUD` (model `Lead`):

```text
/lead/                  lead-list
/lead/new/              lead-create
/lead/<int:pk>/         lead-detail
/lead/<int:pk>/edit/    lead-update
/lead/<int:pk>/delete/  lead-delete
```

The path segment is `url_base` (default: the model name); the URL name is
`{url_name_prefix}-{action}`.

### A subset of actions

Pass names (or `Action` instances) to route only some actions — e.g. read-only:

```python
urlpatterns = [*LeadCRUD.get_urls(["list", "detail"])]
```

### Static routes never get shadowed

`get_urls()` always emits patterns **without** a lookup before those **with**
one. So even with a permissive converter, `/lead/new/` is matched before
`/lead/<slug:pk>/` and never shadowed.

## Independent path and name

`url_base` (the path) and `url_name_prefix` (the reverse names) are separate, so
two views can share a path shape with distinct names, or vice versa:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    url_base = "leads"            # /leads/, /leads/new/, …
    url_name_prefix = "crm_lead"  # crm_lead-list, crm_lead-detail, …
```

## Lookup configuration

By default objects are looked up by `pk` with the `int` converter
(`/lead/<int:pk>/`). To look up by a slug:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    lookup_field = "slug"
    path_converter = "slug"
# → /lead/<slug:slug>/
```

Set `lookup_url_kwarg` only when the URL kwarg name should differ from the model
field. See [Querysets](querysets.md#object-lookup) for the lookup mechanics.

## Reversing inside a view

Use `self.reverse(action, obj=None)` rather than Django's `reverse()` directly —
it builds the right URL name, applies the namespace, and supplies the lookup
kwarg for detail actions:

```python
@action(detail=True, methods=["post"], permission="change")
def qualify(self, request, *args, **kwargs):
    self.object = self.get_object()
    self.object.qualify()
    return HttpResponseRedirect(self.reverse("detail", self.object))
```

`maybe_reverse()` is the forgiving variant: it returns `None` instead of raising
when the action isn't routed. Velcro uses it internally so templates simply omit
links to actions you didn't mount (e.g. no "Delete" link if `delete` isn't in
your `get_urls()`).

## Namespaces just work

`reverse()` reads the namespace from `request.resolver_match` at request time, so
the same class adapts to however it's mounted — including the same urlconf
mounted **twice** under different namespaces:

```python
# crm/urls.py
app_name = "crm"
urlpatterns = [*LeadCRUD.get_urls()]

# project/urls.py
urlpatterns = [
    path("staff/", include("crm.urls", namespace="staff")),    # staff:lead-list
    path("portal/", include("crm.urls", namespace="portal")),  # portal:lead-list
]
```

Under `/staff/`, `self.reverse("detail", obj)` resolves to `staff:lead-detail`;
under `/portal/`, the *same view code* resolves to `portal:lead-detail` — no
configuration. Pin a namespace explicitly with `url_namespace` if you ever need
to override the request-derived one.

> **Note:** mounting under a `namespace=` requires an `app_name` in the included
> module (set `app_name = "crm"` alongside `urlpatterns`, as above). Mounted bare
> with `path("", include("crm.urls"))`, the URL names stay unprefixed
> (`lead-list`) and `reverse()` adapts the same way.

## Cross-model links

The list/detail renderer links a `ForeignKey` cell to the related model's detail
page using the `{related_model_name}-detail` name in the current namespace — so
mounting `AccountCRUD` makes every `account` column across the app clickable,
with no wiring. See
[Fields and value rendering](fields-and-rendering.md#foreignkeys-link-automatically).

## Related

- [Querysets](querysets.md) — lookup fields and converters
- [Custom actions](../customisations/custom-actions.md) — routing your own actions
- [Fields and value rendering](fields-and-rendering.md) — automatic FK links