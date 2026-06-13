# Forms

The `create` and `update` actions render and process a Django form. By default
velcro builds a `ModelForm` from your `fields`, but you can supply your own form
per action and hook into validation and saving.

## What can be customised

| Setting / method     | Default                                  | Purpose                                  |
|----------------------|------------------------------------------|------------------------------------------|
| `form_class`         | `None`                                   | An explicit form for create + update     |
| `{action}_form_class`| `None`                                   | An explicit form for one action          |
| `get_form_class()`   | `form_class`, else a modelform from `fields` | Override to choose the form dynamically |
| `get_form()`         | instantiates the class                   | Override to inject constructor kwargs    |
| `form_valid(form)`   | save → message → redirect/204            | Override for post-save behaviour          |
| `form_invalid(form)` | re-render with errors                    | Override to react to invalid submissions  |

## The default: a generated modelform

With `model` + `fields` and no `form_class`, velcro calls
`modelform_factory(model, fields=get_fields())`:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]
```

**Outcome** — both the create and update forms contain those five inputs, with
Django's default widgets and validation. The form fields follow the resolution
chain, so `create_fields` / `update_fields` shape each form independently (see
[Fields](fields-and-rendering.md)).

## Supplying a form class

Provide a `form_class` to add validation, widgets, or custom fields:

```python
# crm/forms.py
from django import forms
from .models import Lead


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["company_name", "contact_name", "email", "status", "owner"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if email.endswith("@example.com"):
            raise forms.ValidationError("Use a real company email.")
        return email
```

```python
class LeadCRUD(CRUDView):
    model = Lead
    form_class = LeadForm
```

When `form_class` is set, `fields` is no longer required for the form actions
(though you'll still want it for the list/detail views).

## A different form per action

Creation and editing often differ — e.g. `owner` is set at creation and
read-only afterwards. Use the chain:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
    create_form_class = LeadCreateForm
    update_form_class = LeadUpdateForm
```

`create` uses `create_form_class`, `update` uses `update_form_class`, each
falling back to `form_class` then to a generated modelform.

## Injecting constructor arguments

`get_form()` is where the form is instantiated. Override it to pass extra
kwargs — the classic case is handing the form the current user:

```python
def get_form(self, data=None, files=None, **kwargs):
    return super().get_form(data, files, user=self.request.user, **kwargs)
```

Velcro already passes `instance=` (the object being edited, or `None` for
create) and, on `POST`, `data=request.POST` and `files=request.FILES`.

## After a valid submission

`form_valid()` runs on success. The default:

1. `self.object = form.save()`
2. flashes the success message (see [Messages & redirects](messages-and-redirects.md))
3. returns a redirect to `get_success_url()` — or, for an HTMX request with
   `htmx_events` on, a `204` + `HX-Trigger` (see [HTMX](htmx.md)).

Override it to do work around the save — set a field from the request, kick off
a side effect, then defer to `super()`:

```python
def form_valid(self, form):
    form.instance.owner = self.request.user      # stamp the owner
    response = super().form_valid(form)           # saves, messages, redirects
    notify_sales_team(self.object)
    return response
```

If you need the object before `super()` saves it, call `form.save()` yourself —
but then don't call `super().form_valid()` (it would save again); replicate the
message + redirect instead, or factor the side effect to a model/service method.

## After an invalid submission

`form_invalid()` re-renders the form with errors. For a normal request that's
the form page; for an HTMX request it's just the `form` partial, so errors
appear in place without a full reload. Override it to add context or react to
specific errors:

```python
def form_invalid(self, form):
    messages.error(self.request, "Please fix the errors below.")
    return super().form_invalid(form)
```

## Saving business logic elsewhere

Keep `form_valid()` thin. For real workflows — converting a lead, creating
related records — prefer a model method or a service function called from the
view, and consider a [custom action](../customisations/custom-actions.md) rather
than overloading `update`.

## Related

- [Fields and value rendering](fields-and-rendering.md) — how `fields` shapes the form
- [Messages and redirects](messages-and-redirects.md) — what happens after save
- [HTMX](htmx.md) — partial form rendering and inline errors