# Querysets and object lookup

Every action starts from a queryset: the list action iterates it, and detail
actions look an object up inside it. Controlling the queryset is the single most
common — and most important — customisation, because it is how you scope data to
the current user or tenant.

## What can be customised

| Setting / method      | Default                              | Purpose                                  |
|-----------------------|--------------------------------------|------------------------------------------|
| `model`               | `None`                               | The model whose objects are served       |
| `queryset`            | `None`                               | An explicit base queryset                 |
| `get_queryset()`      | `model._default_manager.all()`       | The base queryset for every action        |
| `get_object()`        | lookup by `lookup_field` in queryset | Fetches one object for detail actions     |
| `lookup_field`        | `"pk"`                               | The model field used to look up an object |
| `lookup_url_kwarg`    | `None` (→ `lookup_field`)            | The URL kwarg carrying the lookup value   |
| `path_converter`      | `"int"`                              | The URL converter for the lookup          |

## The default

With just a `model`, the base queryset is `model._default_manager.all()`:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
# get_queryset() → Lead.objects.all()
```

Set `queryset` for a static base (it is cloned per request, so it is safe to
share on the class):

```python
class LeadCRUD(CRUDView):
    queryset = Lead.objects.select_related("owner")
    fields = ["company_name", "owner", "status"]
```

`model` is still worth setting alongside `queryset` — velcro uses it for
permissions, URL names, verbose names, and template discovery.

## Scoping to the request

Override `get_queryset()` whenever the rows depend on the request. This is the
canonical pattern for "users only see their own data":

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status", "owner"]

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)
```

**Outcome** — the list shows only the current user's leads, *and* detail,
update, and delete return **404** for anyone else's lead (the object is looked
up inside this queryset). That is usually what you want: it hides existence
rather than returning 403. Compare with
[object-level permissions](../customisations/access-control.md#object-level-permissions),
which return 403.

### Always call `super()`

`super().get_queryset()` honours `queryset`/`model` and keeps `select_related`
etc. in one place. Returning a bare `Lead.objects.filter(...)` discards any
`queryset` you set.

## Optimising queries

`get_queryset()` is the place for `select_related` / `prefetch_related`. The
list table follows ForeignKeys to build links, so selecting them avoids N+1:

```python
def get_queryset(self):
    return (
        super().get_queryset()
        .select_related("owner")
        .prefetch_related("activities")
    )
```

## The list pipeline

For the **list** action, `get_queryset()` is only the first stage. Velcro then
applies, in order:

```text
get_queryset()  →  filterset  →  search  →  ordering  →  pagination
```

So filtering, search, and ordering all compose *on top of* whatever
`get_queryset()` returns — your scoping is never bypassed. See
[Search, ordering, filtering](search-ordering-filtering.md) and
[Pagination](pagination.md).

## Object lookup

Detail actions (`detail`, `update`, `delete`, and `detail=True` custom actions)
fetch a single object with `get_object()`, which looks up `lookup_field` using
the value in the URL, inside `get_queryset()`:

```python
obj = get_object_or_404(self.get_queryset(), **{self.lookup_field: <url value>})
```

### Looking up by something other than the pk

To use a slug, set the lookup field, the URL kwarg, and a matching converter:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    lookup_field = "slug"          # model field to match
    lookup_url_kwarg = "slug"      # URL kwarg name (defaults to lookup_field)
    path_converter = "slug"        # URL converter
# detail URL → /lead/<slug:slug>/
```

**Outcome** — URLs become `/lead/<slug:slug>/` and reversing
(`self.reverse("detail", obj)`) uses `obj.slug`. `lookup_url_kwarg` only needs
setting when the URL kwarg differs from the model field.

### Overriding `get_object()`

Override it for lookups that aren't a single field match — for example a
composite key or an extra guard. Note that the default `get_object()` also runs
the object-level permission check; preserve that if you rely on it
(call `super()` or replicate the check).

## Related

- [Access control](../customisations/access-control.md) — permissions vs. queryset scoping
- [Search, ordering, filtering](search-ordering-filtering.md) — the rest of the list pipeline
- [URLs and namespaces](urls-and-namespaces.md) — `lookup_field`, converters, reversing