# Access control

Velcro has two independent gates, both off by default:

1. **`login_required`** — is the user authenticated at all?
2. **`permissions`** — does the user hold the right permission for this action?

Both are checked in `dispatch()`, before any handler runs. Object-level checks
additionally run inside `get_object()` for detail actions.

## Requiring login

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    login_required = True
```

| Setting          | Default | Outcome                                                        |
|------------------|---------|----------------------------------------------------------------|
| `login_required` | `False` | `True` → anonymous users are redirected to `settings.LOGIN_URL` |

The redirect preserves the original path as `?next=`, so the user returns after
logging in.

## Model permissions

Set `permissions` to enable per-action permission checks. The convention is the
string `"model"`, which means "enforce each action's default shorthand against
the model's standard Django permissions":

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    permissions = "model"
```

Each action carries a default permission shorthand, expanded against the model:

| Action   | Shorthand | Required permission (model `Lead` in app `crm`) |
|----------|-----------|-------------------------------------------------|
| `list`   | `view`    | `crm.view_lead`                                 |
| `detail` | `view`    | `crm.view_lead`                                 |
| `create` | `add`     | `crm.add_lead`                                  |
| `update` | `change`  | `crm.change_lead`                               |
| `delete` | `delete`  | `crm.delete_lead`                               |

A failed check raises `PermissionDenied` (HTTP 403) — for authenticated and
anonymous users alike.

| Setting       | Default | Outcome                                          |
|---------------|---------|--------------------------------------------------|
| `permissions` | `None`  | No checks. Non-`None` → enforce per-action perms |

> Only the `None`-vs-dict distinction is inspected — any non-`None`, non-dict
> value (the convention is `"model"`) turns on the default shorthand mapping.

## Per-action permission overrides

Pass a dict to override specific actions. Keys are action names; values are a
shorthand, a full `app.codename`, or `None` to require no permission. **Missing
keys fall back to the action's default shorthand.**

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    permissions = {
        "list": None,                 # anyone may list
        "detail": None,               # anyone may view one
        "create": "crm.add_lead",     # explicit, full codename
        # update + delete omitted → fall back to "change" / "delete"
        "qualify": "crm.change_lead", # custom action
    }
```

Shorthands (`view`/`add`/`change`/`delete`) expand against the model; any value
containing a `.` is treated as a full `app.codename` and passes through
untouched.

## Permissions on custom actions

A custom action declares its own default via the `@action(permission=...)`
argument, and it participates in the dict override above by its `name`:

```python
@action(detail=True, methods=["post"], permission="change")
def qualify(self, request, *args, **kwargs):
    ...
```

`GET /lead/<pk>/qualify/` would need `crm.change_lead`. See
[Custom actions](custom-actions.md).

## Object-level permissions

For detail actions (`detail`, `update`, `delete`, and any `detail=True` custom
action), `get_object()` calls `has_permission(obj=...)`. The default
implementation tries the **object-level** check first and falls back to the
**model-level** check:

```python
def has_permission(self, obj=None):
    perm = self.get_required_permission()
    if perm is None:
        return True
    user = self.request.user
    if obj is not None and user.has_perm(perm, obj):
        return True
    return user.has_perm(perm)
```

**Outcome** — object-level backends like
[django-guardian](https://django-guardian.readthedocs.io/) or
[django-rules](https://github.com/dfunckt/django-rules) grant per-object access
automatically, while Django's default backend behaves as plain model
permissions (the `obj` argument is ignored by it).

### Custom authorisation logic

Override `has_permission()` for anything bespoke — ownership, tenancy, status
gates:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    permissions = "model"

    def has_permission(self, obj=None):
        if not super().has_permission(obj=obj):
            return False
        # Reps may only act on their own leads.
        if obj is not None and obj.owner_id != self.request.user.pk:
            return False
        return True
```

## Permissions vs. querysets

Permissions answer "may this user perform this action?". To control **which
rows exist at all** (so a user simply never sees other people's leads), filter
the queryset instead — the two compose well:

```python
def get_queryset(self):
    return super().get_queryset().filter(owner=self.request.user)
```

Filtering the queryset turns "forbidden" (403) into "not found" (404) for rows
the user shouldn't know about. See [Querysets](../guides/querysets.md).

## What each method does

| Method                       | Role                                                              |
|------------------------------|-------------------------------------------------------------------|
| `dispatch()`                 | Runs the login + model-level permission gate before the handler   |
| `get_required_permission()`  | Resolves the permission string for the current action (or `None`) |
| `has_permission(obj=None)`   | Returns whether the user holds it; override for custom logic       |

## Related

- [Querysets](../guides/querysets.md) — row-level scoping
- [Custom actions](custom-actions.md) — per-action permissions
- [Defaults](../references/defaults.md#access-control-defaults)