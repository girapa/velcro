# Custom actions

The five built-in actions (`list`, `create`, `detail`, `update`, `delete`)
cover CRUD. A real application needs more: qualify a lead, convert it to an
account, mark a deal won, export a report. In velcro these are **actions** too —
the action system is open, not a closed enum.

There are three ways to work with actions:

1. **`@action`** — add a new operation as a decorated view method.
2. **`Action.using()`** — tweak a built-in without redefining it.
3. **`extra_actions`** — register `Action` instances directly.

## What an `Action` is

An `Action` is a frozen dataclass describing one operation:

| Field             | Meaning                                                             | Default |
|-------------------|--------------------------------------------------------------------|---------|
| `name`            | View-method name, URL name suffix, and config-lookup prefix        | —       |
| `handlers`        | HTTP method → view-method name, e.g. `{"get": "list"}`             | `{}`    |
| `url_pattern`     | URL fragment after `url_base`; may contain `{lookup}`             | `""`    |
| `detail`          | Operates on a single object (needs a lookup + `get_object()`)      | `False` |
| `template_suffix` | Suffix for template discovery (`None` = no template of its own)    | `None`  |
| `permission`      | Default permission shorthand or full `app.codename`                | `None`  |

## The `@action` decorator

Decorate a method on your `CRUDView`. The method *is* the handler.

```python
from django.contrib import messages
from django.http import HttpResponseRedirect
from velcro import CRUDView, action
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]

    @action(detail=True, methods=["post"], permission="change")
    def qualify(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = Lead.Status.QUALIFIED
        self.object.save(update_fields=["status"])
        messages.success(request, f"{self.object} was qualified.")
        return HttpResponseRedirect(self.reverse("detail", self.object))
```

**Outcome** — this routes:

```text
POST /lead/<int:pk>/qualify/    lead-qualify
```

A `GET` to that URL returns `405 Method Not Allowed` (only `post` is declared),
and with permissions enabled it requires `crm.change_lead`.

### `@action` parameters

| Parameter         | Default                                  | Effect                                                       |
|-------------------|------------------------------------------|--------------------------------------------------------------|
| `detail`          | (required)                               | `True` → URL gets `{lookup}` and a single-object lookup      |
| `methods`         | `["get"]`                                | HTTP methods that route to this method                       |
| `url_pattern`     | `{lookup}/{name}` or `{name}`            | Override the URL fragment entirely                           |
| `name`            | the method name                          | Override the action name (URL name + config prefix)          |
| `template_suffix` | `_{name}` for `GET` actions, else `None` | Suffix for template discovery                                |
| `permission`      | `None`                                   | Permission shorthand or full `app.codename`                  |

### A `GET` action that renders a page

Give it a `GET` handler and velcro derives a template suffix of `_{name}`, so it
renders through the normal template chain. A `pipeline` report for the sales
team:

```python
class DealCRUD(CRUDView):
    model = Deal
    fields = ["name", "account", "amount", "stage"]

    @action(detail=False, methods=["get"], permission="view")
    def pipeline(self, request, *args, **kwargs):
        self.object_list = self.get_queryset().exclude(
            stage__in=[Deal.Stage.WON, Deal.Stage.LOST]
        )
        context = self.get_context_data(total=sum(d.amount for d in self.object_list))
        return self.render_to_response(context)
```

**Outcome** — `GET /deal/pipeline/` named `deal-pipeline`, rendered from
`crm/deal_pipeline.html` (falling back to `velcro/object_pipeline.html`, which
does not exist by default — so provide the app template). See
[Templates](templates.md) for discovery rules.

### Per-action config still applies

Because the action's `name` is `qualify`, the resolution chain looks up
`qualify_success_message`, `qualify_template_name`, `qualify_success_url`, and
so on before the general attribute:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    qualify_success_message = "{object} is now qualified — nice work."

    @action(detail=True, methods=["post"], permission="change")
    def qualify(self, request, *args, **kwargs):
        self.object = self.get_object()
        qualify_lead(lead=self.object, actor=request.user)
        self.send_success_message()
        return HttpResponseRedirect(self.get_success_url())
```

## Tweaking a built-in with `using()`

`Action.using()` returns a copy with fields replaced — change a built-in's URL
or permission without rewriting it. Register the result via `extra_actions`
(it replaces the default of the same `name`):

```python
from velcro import CRUDView, UPDATE, DELETE
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    extra_actions = [
        UPDATE.using(url_pattern="{lookup}/change"),   # /lead/<pk>/change/
        DELETE.using(permission="crm.archive_lead"),   # custom permission
    ]
```

## Registering actions with `extra_actions`

For full control, construct `Action` instances directly. `extra_actions` is
merged after the defaults, so a same-named entry overrides a default; a new name
adds an operation.

```python
from velcro import CRUDView, Action, LOOKUP
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    extra_actions = [
        Action(
            name="archive",
            handlers={"post": "archive"},
            url_pattern=f"{LOOKUP}/archive",
            detail=True,
            permission="change",
        ),
    ]

    def archive(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.archive()
        return HttpResponseRedirect(self.reverse("list"))
```

`LOOKUP` is the placeholder (`"{lookup}"`) velcro substitutes with the view's
`<converter:kwarg>` fragment at URL-generation time.

## How actions are assembled

`get_actions()` builds the registry in order, later entries overriding earlier
ones by `name`:

1. `DEFAULT_ACTIONS` (the five built-ins)
2. `extra_actions`
3. `@action`-decorated methods (MRO-aware: subclasses override base classes)

Override `get_actions()` for complete control — for example to drop an action
entirely.

## Selecting which actions are routed

`get_urls()` takes an optional list to route a subset — names or `Action`
instances. A read-only view:

```python
urlpatterns = [*LeadCRUD.get_urls(["list", "detail"])]
```

Static routes (like `/lead/new/`) are always emitted before lookup routes (like
`/lead/<pk>/`), so a permissive converter never shadows them. See
[URLs and namespaces](../guides/urls-and-namespaces.md).

## Related

- [URLs and namespaces](../guides/urls-and-namespaces.md) — routing and reversing
- [Access control](access-control.md) — the `permission` field in practice
- [Templates](templates.md) — templates for `GET` actions
- [Messages and redirects](../guides/messages-and-redirects.md) — `send_success_message()`, `get_success_url()`