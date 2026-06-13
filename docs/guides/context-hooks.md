# Context hooks

Every template render is fed a context dict built by `get_context_data()`. You
extend it either globally (override `get_context_data()`) or per action (define
`get_{action}_context_data()`), and you can rename the object keys.

## What can be customised

| Setting / method                | Default                  | Purpose                                  |
|---------------------------------|--------------------------|------------------------------------------|
| `context_object_name`           | `None` (→ model name)    | Name of the object / object-list key      |
| `get_context_data(**kwargs)`    | builds the base context  | Override to add keys for every action     |
| `get_{action}_context_data(ctx)`| not defined              | Per-action hook, runs after the base       |
| `get_context_object_name()`     | resolves the name        | Override the object key naming            |

## What's always in the context

`get_context_data()` provides a consistent base:

| Key                          | When            | Contents                                       |
|------------------------------|-----------------|------------------------------------------------|
| `view`                       | always          | The view instance                              |
| `action`                     | always          | The current action's name                      |
| `base_template_name`         | always          | The base template to extend                    |
| `object_verbose_name`        | with a model    | Singular verbose name                          |
| `object_verbose_name_plural` | with a model    | Plural verbose name                            |
| `list_view_url`              | always          | Reversed list URL, or `None`                   |
| `create_view_url`            | always          | Reversed create URL, or `None`                 |
| `object`                     | detail/form     | The instance                                   |
| `detail_view_url` / `update_view_url` / `delete_view_url` | detail/form | Reversed per-object URLs, or `None` |
| `object_fields`              | detail          | List of `Cell` for the detail page             |
| `<model>` (e.g. `lead`)      | detail/form     | The instance, under its named key              |
| `object_list`                | list            | The (paged) queryset                           |
| `object_table`               | list            | `{"headers": [...], "rows": [Row, ...]}`       |
| `<model>_list` (e.g. `lead_list`) | list       | The queryset, under its named key              |
| `page_obj` / `paginator` / `is_paginated` | list | Pagination state (see [Pagination](pagination.md)) |
| `filterset` / `search_*`     | list            | Filtering and search state                     |

## The per-action hook (preferred)

Define `get_{action}_context_data(context)` to add keys for **one** action only.
It receives the already-built context and returns it. This is the cleanest way
to enrich a single view:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]

    def get_list_context_data(self, context):
        context["new_this_week"] = self.get_queryset().filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        return context

    def get_detail_context_data(self, context):
        context["recent_activities"] = context["object"].activities.all()[:5]
        return context
```

The hook runs **after** the base context is assembled, so `context["object"]`
and the rest are available. It works for custom actions too — a `pipeline`
action looks up `get_pipeline_context_data`.

## Global additions

Override `get_context_data()` to add keys for **every** action. Always call
`super()` and add to its result:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context["nav_section"] = "sales"
    return context
```

Prefer the per-action hook when the extra data only matters to one action — it
keeps each action's concerns separate and avoids recomputing things.

## Renaming the object keys

By default the instance is exposed under the lowercased model name (`lead`) and
the list under `<model>_list` (`lead_list`), in addition to the generic `object`
/ `object_list`. Override with `context_object_name`:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    context_object_name = "record"
# templates can use {{ record }} / {{ record_list }}
```

`object` and `object_list` remain available regardless, so the bundled templates
keep working.

## Related

- [Templates](../customisations/templates.md) — consuming the context
- [Fields and value rendering](fields-and-rendering.md) — what `object_fields` / `object_table` contain
- [Pagination](pagination.md) — the pagination context keys