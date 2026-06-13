# Core concepts

Velcro is built around three concepts:

1. `CRUDView`
2. `Action`
3. Per-action customisation

## `CRUDView`

A `CRUDView` is one class that serves multiple operations for a model:

- list
- create
- detail
- update
- delete

```python
from velcro import CRUDView
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
```

A single class serves every action. Each generated URL binds the class to one
action via `as_view(action=...)`, which wires that action's HTTP handlers onto
the instance for the request. You configure the class once; velcro decides
which behaviour applies based on the action being served.

Mounted with `get_urls()`, this generates the five standard CRUD URL patterns:

```python
# crm/urls.py
urlpatterns = [*LeadCRUD.get_urls()]
```

## `Action`

An `Action` describes one operation a `CRUDView` can perform. It is a frozen
dataclass holding:

- `name` — used for the view-method name, URL name, and config lookups
- `handlers` — a map of HTTP method to view-method name, e.g. `{"get": "list"}`
- `url_pattern` — the URL fragment it contributes
- `detail` — whether it operates on a single object (needs a lookup)
- `template_suffix` — the suffix used to find its template
- `permission` — the default permission shorthand

Velcro ships with five built-in actions:

| Action   | Purpose                       | URL fragment      |
|----------|-------------------------------|-------------------|
| `list`   | Show a collection of objects  | (empty)           |
| `create` | Create a new object           | `new/`            |
| `detail` | Show one object               | `<int:pk>/`       |
| `update` | Edit one object               | `<int:pk>/edit/`  |
| `delete` | Delete one object             | `<int:pk>/delete/`|

Unlike a closed enum, actions are open: you can add, replace, or tweak them.
Add your own with the `@action` decorator (see
[Custom actions](customisations/custom-actions.md)), or adjust a built-in
without redefining it — `UPDATE.using(url_pattern="{lookup}/change")`.

## Per-action customisation

Most settings resolve through one lookup chain:

```text
{action}_{name}  ->  {name}  ->  default
```

So an action-specific attribute wins, falling back to the general attribute,
falling back to velcro's default. Learn the chain once; it applies everywhere
(`list_fields` → `fields`, `update_form_class` → `form_class`,
`detail_template_name` → `template_name`, and so on).

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
    list_fields = ["company_name", "status"]
    update_fields = ["company_name", "contact_name", "email", "status", "notes"]
```

- The `list` action uses `list_fields`.
- The `update` action uses `update_fields`.
- Every other action falls back to `fields`.

The same chain drives method-level overrides too: define
`get_{action}_context_data(context)` and it runs only for that action (see
[Context hooks](guides/context-hooks.md)).

## Where to go next

- The complete map of customisation points:
  [Customisation overview](customisations/overview.md)
- Every default value and its outcome: [Defaults](references/defaults.md)
- Every public attribute and method: [API tree](references/api-tree.md)