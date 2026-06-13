# Templates

Velcro ships bundled templates for every built-in action. They are semantic
HTML with stable `velcro-*` classes and **no styling**, so you can apply any CSS
framework or none. You override them at three levels of granularity: the whole
template, a named block, or — for HTMX — a named partial.

## The bundled templates

| Action   | Suffix            | Bundled template                          |
|----------|-------------------|-------------------------------------------|
| `list`   | `_list`           | `velcro/object_list.html`                 |
| `create` | `_form`           | `velcro/object_form.html`                 |
| `update` | `_form`           | `velcro/object_form.html`                 |
| `detail` | `_detail`         | `velcro/object_detail.html`               |
| `delete` | `_confirm_delete` | `velcro/object_confirm_delete.html`       |

Each one `{% extends base_template_name %}` and fills its `content` block, so
your project's `base.html` controls the surrounding page.

## Discovery order

For an action with template suffix `<suffix>`, `get_template_names()` returns,
in order:

```text
{template_dir or app_label}/{model}{suffix}.html
velcro/object{suffix}.html
```

For `LeadCRUD` (model in app `crm`) on the detail action:

```text
crm/lead_detail.html      ← your override, if it exists
velcro/object_detail.html ← bundled fallback
```

**Outcome** — drop a file at the first path and it wins; otherwise the bundled
template is used. You never have to copy a template you don't want to change.

## What can be customised

| Setting                  | Default                  | Effect                                                       |
|--------------------------|--------------------------|--------------------------------------------------------------|
| `base_template_name`     | `"base.html"`            | The template the bundled templates extend                    |
| `template_dir`           | `None` (→ `app_label`)   | First path segment in discovery (for views in another app)   |
| `template_name`          | `None`                   | Skip discovery; use this template for every action           |
| `{action}_template_name` | `None`                   | As above, for one action                                     |
| `template_name_suffix`   | the action's suffix      | Override the suffix used in discovery                        |

### Point at a custom base template

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    base_template_name = "crm/base.html"
```

Your base template needs a `content` block:

```html
{% block content %}{% endblock content %}
```

### Views that live in a different app from their model

If `LeadCRUD` lives in a `dashboard` app but `Lead` lives in `crm`, discovery
would look under `crm/`. Point it elsewhere with `template_dir`:

```python
class LeadCRUD(CRUDView):
    model = Lead              # app_label = "crm"
    template_dir = "dashboard"
    fields = ["company_name", "status"]
# → dashboard/lead_list.html, dashboard/lead_detail.html, …
```

### One fixed template

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    list_template_name = "crm/leads_table.html"   # list only
    # template_name = "crm/generic.html"          # every action
```

## Overriding a block, not the whole template

The bundled templates name their regions with `{% block %}`. Extend the bundled
template and override just the block you care about:

```html
{# crm/lead_list.html #}
{% extends "velcro/object_list.html" %}

{% block velcro_search %}
  <p class="hint">Search by company, contact, or email.</p>
  {{ block.super }}
{% endblock %}
```

Available blocks:

| Template                      | Blocks                                                           |
|-------------------------------|-----------------------------------------------------------------|
| `object_list.html`            | `content`, `velcro_messages`, `velcro_search`, `velcro_filters`, `velcro_table` |
| `object_detail.html`          | `content`, `velcro_messages`, `velcro_fields`                   |
| `object_form.html`            | `content`, `velcro_messages`                                    |
| `object_confirm_delete.html`  | `content`, `velcro_messages`                                    |

## Partials (HTMX swap targets)

The list and form templates declare swappable regions with Django 6's core
`{% partialdef %}`:

- `object_list.html` → the `table` partial (the `<table>` + pagination)
- `object_form.html` → the `form` partial (the `<form>` element)

When a request carries `HX-Request`, velcro renders only the partial named in
`htmx_partials` for that action. Crucially, **partials resolve through the same
discovery chain**: if you override `crm/lead_list.html` without defining a
`table` partial, the partial request falls back to the bundled template's
`table`. See [HTMX](../guides/htmx.md) for the request/response protocol.

## The context templates receive

Templates stay dumb — they loop over data velcro prepares. The most useful keys:

| Key                          | Available in | Contents                                              |
|------------------------------|--------------|-------------------------------------------------------|
| `object`                     | detail, form | The instance                                          |
| `object_fields`              | detail       | List of `Cell` (label, value, optional url)           |
| `object_list`                | list         | The page (or full) queryset                           |
| `object_table`               | list         | `{"headers": [...], "rows": [Row, ...]}`              |
| `form`                       | create/update| The bound/unbound form                                |
| `object_verbose_name(_plural)` | all        | For headings                                          |
| `*_view_url`                 | all          | `list_view_url`, `create_view_url`, `detail_view_url`, `update_view_url`, `delete_view_url` (each `None` if not routed) |
| `page_obj`, `is_paginated`, `paginator` | list | Pagination state                                  |

`Cell` and `Row` come from `velcro.renderers` — see
[Fields and value rendering](../guides/fields-and-rendering.md) for how each
cell's value and link are computed. To add your own keys, use
[context hooks](../guides/context-hooks.md).

## Styling

The markup carries stable `velcro-*` classes (`velcro-list`, `velcro-table`,
`velcro-action`, `velcro-sort-asc`, `velcro-messages`, …) and no inline styles.
Target them from your stylesheet, or replace the templates entirely.