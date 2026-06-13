# Defaults reference

Every default velcro applies, and the outcome of each. Remember that most
settings resolve through `{action}_{name}  ->  {name}  ->  default`, so the
"Default" column is the final fallback when no attribute is set.

## Built-in actions

| Action   | HTTP methods  | URL fragment      | Detail | Template suffix   | Permission |
|----------|---------------|-------------------|:------:|-------------------|------------|
| `list`   | `GET`         | (empty)           |   No   | `_list`           | `view`     |
| `create` | `GET`, `POST` | `new`             |   No   | `_form`           | `add`      |
| `detail` | `GET`         | `{lookup}`        |  Yes   | `_detail`         | `view`     |
| `update` | `GET`, `POST` | `{lookup}/edit`   |  Yes   | `_form`           | `change`   |
| `delete` | `GET`, `POST` | `{lookup}/delete` |  Yes   | `_confirm_delete` | `delete`   |

`GET` on a form action renders the form; `POST` processes it. `GET` on `delete`
renders the confirmation page; `POST` performs the deletion. The permission
shorthand only applies when `permissions` is enabled.

## Core configuration

| Setting               | Default | Outcome                                                  |
|-----------------------|---------|----------------------------------------------------------|
| `model`               | `None`  | Required unless `queryset` and `get_*` methods are given |
| `fields`              | `None`  | Required for the list table, detail view, and modelforms |
| `queryset`            | `None`  | Falls back to `model._default_manager.all()`             |
| `form_class`          | `None`  | Falls back to a modelform built from `fields`            |
| `context_object_name` | `None`  | Falls back to `<model>` / `<model>_list`                 |
| `extra_actions`       | `None`  | No extra actions beyond defaults and `@action` methods   |

## URL defaults

| Setting            | Default      | Outcome                                          |
|--------------------|--------------|--------------------------------------------------|
| `url_base`         | model name   | Path prefix for generated URLs                   |
| `url_name_prefix`  | `url_base`   | Prefix for generated URL *names*                 |
| `lookup_field`     | `"pk"`       | Model field used to look up an object            |
| `lookup_url_kwarg` | `None`       | Falls back to `lookup_field`                     |
| `path_converter`   | `"int"`      | Detail URLs use `<int:pk>`                        |
| `url_namespace`    | `None`       | Namespace read from the request when reversing   |

## Fields and forms

| Setting       | Default | Outcome                                                       |
|---------------|---------|---------------------------------------------------------------|
| `fields`      | `None`  | Drives list columns, detail rows, and the generated modelform |
| `form_class`  | `None`  | When unset, a modelform is generated from `fields`            |

`get_fields()` raises `ImproperlyConfigured` if neither `fields` (nor
`{action}_fields`) nor a `form_class` is available for a form action.

## Template defaults

| Setting               | Default       | Outcome                                          |
|-----------------------|---------------|--------------------------------------------------|
| `base_template_name`  | `"base.html"` | The template the bundled templates extend        |
| `template_dir`        | `None`        | Falls back to the model's `app_label`            |
| `template_name`       | `None`        | When unset, discovery uses the suffix chain below |
| `template_name_suffix`| action's      | Set per action (`_list`, `_form`, …)             |

Template discovery order:

```text
{template_dir or app_label}/{model}{suffix}.html
velcro/object{suffix}.html
```

## Context defaults

`get_context_data()` always provides: `view`, `action`, `base_template_name`,
`object_verbose_name`, `object_verbose_name_plural`, `list_view_url`,
`create_view_url`. Detail/form actions add `object`, `detail_view_url`,
`update_view_url`, `delete_view_url`, `object_fields`. The list action adds
`object_list`, `object_table`, plus pagination keys. See
[Context hooks](../guides/context-hooks.md) for the full list.

## Search, ordering, filtering defaults

| Setting            | Default      | Outcome                                          |
|--------------------|--------------|--------------------------------------------------|
| `search_fields`    | `None`       | No search box; `?q=` ignored                     |
| `search_param`     | `"q"`        | Query string parameter for search                |
| `ordering_fields`  | `None`       | No sortable columns; `?ordering=` ignored        |
| `ordering_param`   | `"ordering"` | Query string parameter for ordering              |
| `filterset_class`  | `None`       | No filter form unless set or `filterset_fields`  |
| `filterset_fields` | `None`       | No filter form; requires the `filter` extra      |

## Pagination defaults

| Setting       | Default  | Outcome                                          |
|---------------|----------|--------------------------------------------------|
| `paginate_by` | `None`   | No pagination — the whole queryset is listed     |
| `page_kwarg`  | `"page"` | Query string / URL kwarg for the page number     |
| `allow_empty` | `True`   | An empty list renders; set `False` to 404 it     |

## Access control defaults

| Setting          | Default | Outcome                                          |
|------------------|---------|--------------------------------------------------|
| `login_required` | `False` | Anonymous users are allowed                       |
| `permissions`    | `None`  | No permission checks                              |

When `permissions` is a non-`None` value (the convention is `"model"`), each
action enforces its default shorthand (`view`/`add`/`change`/`delete`) against
the model's standard permissions. A dict overrides specific actions; missing
keys fall back to the shorthand. A failed check raises `PermissionDenied`.

## Messages and redirects

| Setting           | Default  | Outcome                                          |
|-------------------|----------|--------------------------------------------------|
| `success_message` | `None`   | Create/update/delete use a default message       |
| `redirect_param`  | `"next"` | A safe `?next=` value overrides the success URL   |
| `success_url`     | `None`   | Falls back to the detail page, then the list      |

When `success_message` is `None`, create/update/delete flash a default
("Lead created.", "Lead updated.", "Lead deleted."). Set `success_message = ""`
to disable a message. When `success_url` is `None`, velcro redirects to the
saved object's detail view, falling back to the list (and to the list after a
deletion).

## HTMX defaults

| Setting         | Default                                                 | Outcome                                  |
|-----------------|---------------------------------------------------------|------------------------------------------|
| `htmx_partials` | `{"list": "table", "create": "form", "update": "form"}` | Which partial each action returns to HTMX |
| `htmx_events`   | `True`                                                  | Mutations reply `204` + `HX-Trigger`     |

Genuine `HX-Request` calls (excluding `hx-boosted` navigation) receive only the
named partial. Successful HTMX mutations respond `204` with an
`HX-Trigger: {"<model>Changed": {"action": ..., "pk": ...}}` header. Set
`htmx_events = False` for normal redirects.