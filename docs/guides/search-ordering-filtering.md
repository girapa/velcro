# Search, ordering, filtering

Three independent layers refine the list view, all driven by the query string.
Search and ordering have **no dependencies**; filtering uses the optional
`django-filter` (the `velcro[filter]` extra) and is only imported when you
configure it.

## The list pipeline

They compose in a fixed order, each on top of the last, after your
`get_queryset()`:

```text
get_queryset()  →  filterset  →  search  →  ordering  →  pagination
```

So a filtered-and-searched list is an `AND` of both, ordered last. None of this
bypasses your queryset scoping (see [Querysets](querysets.md)).

---

## Search

| Setting / method     | Default | Purpose                                  |
|----------------------|---------|------------------------------------------|
| `search_fields`      | `None`  | Fields to search; enables the search box |
| `search_param`       | `"q"`   | Query-string parameter                    |
| `get_search_query()` | `?q` value, stripped | Override the source of the term |
| `apply_search()`     | builds the `Q` filter | Override the matching logic     |

Set `search_fields` to enable a search box (`?q=`):

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
    search_fields = ["company_name", "contact_name", "email"]
```

**Outcome** — `GET /lead/?q=acme` returns leads where any listed field matches,
combined with `OR`. By default matching is case-insensitive *contains*. Admin
prefixes tune that per field:

| Prefix | Lookup         | Example       | Matches                |
|--------|----------------|---------------|------------------------|
| (none) | `icontains`    | `company_name`| anywhere in the value  |
| `^`    | `istartswith`  | `^company_name`| start of the value    |
| `=`    | `iexact`       | `=email`      | the whole value        |

```python
search_fields = ["^company_name", "=email", "contact_name", "account__name"]
```

Relation-spanning lookups (`account__name`) are allowed; velcro adds
`.distinct()` automatically when any field spans a relation, to avoid duplicate
rows.

---

## Ordering

| Setting / method        | Default      | Purpose                              |
|-------------------------|--------------|--------------------------------------|
| `ordering_fields`       | `None`       | Whitelist of sortable fields          |
| `ordering_param`        | `"ordering"` | Query-string parameter                |
| `get_current_ordering()`| validated `?ordering` | Override the source            |
| `apply_ordering()`      | `order_by(*ordering)` | Override how it's applied      |

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status", "created_at"]
    ordering_fields = ["company_name", "status", "created_at"]
```

**Outcome** — `GET /lead/?ordering=-created_at,company_name` orders newest
first, then by company name. The value is a comma-separated list; a leading `-`
means descending.

`ordering_fields` is a **whitelist**: any requested field not in it is silently
dropped, so the query string can never order by an arbitrary column. When
empty/unset, `?ordering` is ignored entirely.

### Sortable column headers

When a list column's field is in `ordering_fields`, velcro renders its header as
a sort link with a ▲ (asc) / ▼ (desc) indicator, and clicking toggles the
direction. This is built into the bundled list template — nothing else to wire
up. (The column must be both a displayed field and in `ordering_fields`.)

---

## Filtering

| Setting / method      | Default | Purpose                                      |
|-----------------------|---------|----------------------------------------------|
| `filterset_fields`    | `None`  | Fields to build a filter form from           |
| `filterset_class`     | `None`  | An explicit `django_filters.FilterSet`       |
| `get_filterset_class()` | resolves the two above | Override to choose dynamically  |
| `get_filterset()`     | instantiates with `request.GET` | Override construction      |

Filtering requires `django-filter`:

```bash
pip install "velcro[filter] @ git+https://github.com/girapa/velcro.git"
```

The quick path — let velcro build a filterset from field names:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status", "owner"]
    filterset_fields = ["status", "owner"]
```

**Outcome** — a filter form renders above the table, and `GET
/lead/?status=qualified&owner=3` narrows the list. If `filterset_fields` (or
`filterset_class`) is set but `django-filter` isn't installed, velcro raises
`ImproperlyConfigured` with an install hint.

For full control — custom widgets, lookups, method filters — supply a
`FilterSet`:

```python
import django_filters
from .models import Lead


class LeadFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="gte"
    )

    class Meta:
        model = Lead
        fields = ["status", "owner"]


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status", "owner"]
    filterset_class = LeadFilter
```

`filterset_class` wins over `filterset_fields` when both are set.

---

## All three together

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "status", "owner", "created_at"]
    search_fields = ["company_name", "contact_name", "email"]
    ordering_fields = ["company_name", "created_at", "status"]
    filterset_fields = ["status", "owner"]
```

```text
/lead/?q=acme
/lead/?status=qualified
/lead/?ordering=-created_at
/lead/?q=acme&status=qualified&ordering=company_name
```

The bundled list template renders the search box, the filter form, and sortable
headers, all composed with Django's `{% querystring %}` tag so parameters
survive one another (sorting keeps your search and filters intact).

## Related

- [Querysets](querysets.md) — the first stage of the pipeline
- [Pagination](pagination.md) — the last stage
- [Templates](../customisations/templates.md) — the `velcro_search` / `velcro_filters` blocks