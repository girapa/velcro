# Messages and redirects

After a successful create, update, or delete, velcro does two things: flashes a
success message and redirects somewhere sensible. Both are configurable through
the per-action chain, and both have safe defaults.

## What can be customised

| Setting / method            | Default            | Purpose                                   |
|-----------------------------|--------------------|-------------------------------------------|
| `success_message`           | `None`             | The flash message text                    |
| `{action}_success_message`  | `None`             | Message for one action                     |
| `success_url`               | `None`             | Where to redirect after success            |
| `{action}_success_url`      | `None`             | Redirect target for one action             |
| `redirect_param`            | `"next"`           | Query/POST param that can override the URL |
| `get_success_message()`     | builds the default | Override message logic                     |
| `get_success_url()`         | resolves the chain | Override redirect logic                    |

---

## Messages

### The default

With nothing set, create/update/delete flash a default built from the model's
verbose name:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
```

**Outcome** — "Lead created.", "Lead updated.", "Lead deleted." (other actions
get no message by default). Messages are sent via `django.contrib.messages`
with `fail_silently=True`, so nothing breaks if the messages framework isn't
installed — it just becomes a no-op.

### Custom text and placeholders

Set `success_message` (for all actions) or `{action}_success_message` (for one).
The text supports two placeholders, `{object}` and `{verbose_name}`:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    success_message = "Saved {object}."
    delete_success_message = "{object} was permanently deleted."
    create_success_message = "New {verbose_name}: {object}."
```

### Disabling a message

An empty string disables the message for that action:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    update_success_message = ""     # silent updates
```

### Custom actions

A custom action flashes a message by calling `self.send_success_message()`,
which resolves `{action}_success_message` by the action's `name`:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    qualify_success_message = "{object} is now qualified."

    @action(detail=True, methods=["post"], permission="change")
    def qualify(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.qualify()
        self.send_success_message()
        return HttpResponseRedirect(self.get_success_url())
```

---

## Redirects

### The default policy

`get_success_url()` resolves in this order:

1. A **safe `?next=`** value (see below).
2. `{action}_success_url`, then `success_url`.
3. **Default policy**: the saved object's **detail** page; after a **delete**,
   the **list** page. (If detail isn't routed, it falls back to the list.)

So out of the box, creating or updating a lead lands on that lead's detail page,
and deleting one returns to the list — no configuration.

### Setting an explicit target

`success_url` can be a path or a lazy reverse. Use the chain for per-action
targets:

```python
from django.urls import reverse_lazy


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    success_url = reverse_lazy("lead-list")      # always back to the list
    create_success_url = reverse_lazy("lead-list")
```

### The `next` parameter

By default a `?next=` (or POSTed `next`) value overrides the success URL — handy
for "edit, then return where I came from" flows. The bundled form template
forwards `request.GET.next` as a hidden input automatically.

The value is **validated** with `url_has_allowed_host_and_scheme` against the
current host (and HTTPS when the request is secure), so it can't be used as an
open redirect. Change the parameter name, or disable the behaviour entirely:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    redirect_param = None       # ignore ?next= everywhere
```

### Fully custom

Override `get_success_url()` for logic that depends on the object or request:

```python
def get_success_url(self):
    if self.object.status == Lead.Status.QUALIFIED:
        return self.reverse("detail", self.object)
    return self.reverse("list")
```

If velcro can't determine any URL (no `success_url`, and neither detail nor list
is routed) it raises `ImproperlyConfigured` rather than redirecting nowhere.

---

## HTMX interaction

When the request is a genuine HTMX call and `htmx_events` is on, successful
mutations skip the redirect and reply `204` + an `HX-Trigger` event instead. The
success **message** is still flashed (ready for the next render). Set
`htmx_events = False` to fall back to normal redirects. See [HTMX](htmx.md).

## Related

- [Forms](forms.md) — `form_valid()` calls these
- [Custom actions](../customisations/custom-actions.md) — `send_success_message()` / `get_success_url()`
- [HTMX](htmx.md) — the `204` mutation response