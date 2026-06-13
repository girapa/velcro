# Pagination

Pagination is the final stage of the list pipeline. It is **off by default** —
set `paginate_by` to turn it on.

## What can be customised

| Setting / method        | Default  | Purpose                                       |
|-------------------------|----------|-----------------------------------------------|
| `paginate_by`           | `None`   | Page size; `None` lists the whole queryset     |
| `{action}_paginate_by`  | `None`   | Page size for one action                       |
| `page_kwarg`            | `"page"` | Query-string / URL kwarg for the page number   |
| `allow_empty`           | `True`   | Whether an empty list renders or 404s          |
| `get_paginate_by()`     | resolves `paginate_by` | Override for a dynamic page size |
| `get_paginator()`       | Django `Paginator`      | Override for a custom paginator  |
| `paginate_queryset()`   | returns the `Page`      | Override the pagination mechanics |

## The default

No `paginate_by` means no pagination — the list renders every row:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
# whole queryset on one page
```

## Turning it on

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    paginate_by = 25
```

**Outcome** — the list shows 25 rows per page and the bundled template renders
Previous / Next links and a "Page X of Y" indicator. Navigate with
`?page=2`. The page number is read from the URL kwarg `page_kwarg` first, then
the query string, defaulting to page 1.

`?page=last` jumps to the final page. An out-of-range or non-integer page (other
than `last`) raises `Http404`.

## Per-action page size

Pagination only applies to list-style actions, but a custom `GET` action that
sets `self.object_list` paginates too, and can have its own size via the chain:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    paginate_by = 25
    list_paginate_by = 50      # the main list shows 50; other paginated actions, 25
```

## Empty lists

By default an empty list renders the template's "No leads yet." empty state. To
404 instead when there are no results:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    allow_empty = False
```

## Dynamic page size

Override `get_paginate_by()` to vary the size at request time — e.g. honour a
user preference or a `?per_page=` parameter:

```python
def get_paginate_by(self):
    try:
        return min(int(self.request.GET.get("per_page", 25)), 100)
    except ValueError:
        return 25
```

## Context for templates

When pagination is active, the list context carries:

| Key            | Contents                                            |
|----------------|-----------------------------------------------------|
| `page_obj`     | The current `Page` (`object_list`, `has_next`, …)   |
| `paginator`    | The `Paginator`                                     |
| `is_paginated` | `True` when there is more than one page             |

`object_list` is the current page's rows (not the full queryset) when paginated.
The bundled template builds its links with `{% querystring page=... %}`, so
search, ordering, and filter parameters are preserved across pages.

## Related

- [Search, ordering, filtering](search-ordering-filtering.md) — the stages before pagination
- [Templates](../customisations/templates.md) — the pagination markup