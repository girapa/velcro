# HTMX

Velcro speaks [HTMX](https://htmx.org/) natively, with a pure header/partial
protocol. **No JavaScript is shipped**, and nothing breaks for non-HTMX clients —
the same views serve full pages or partials depending on the request headers.

## What can be customised

| Setting / method            | Default                                                 | Purpose                                      |
|-----------------------------|---------------------------------------------------------|----------------------------------------------|
| `htmx_partials`             | `{"list": "table", "create": "form", "update": "form"}` | Which partial each action returns to HTMX    |
| `htmx_events`               | `True`                                                  | Whether mutations reply `204` + `HX-Trigger` |
| `is_htmx`                   | property                                                | Whether the request is a genuine HTMX call   |
| `get_htmx_partial()`        | reads `htmx_partials`                                    | Override partial selection                   |
| `get_htmx_event_name()`     | `<model>Changed`                                         | Override the trigger event name              |
| `htmx_success_response()`   | `204` + `HX-Trigger`                                    | Override the mutation response               |

## How a request is detected

`is_htmx` is `True` when the request carries `HX-Request: true` **and** is not
`hx-boosted` (boosted navigation wants a full page). Only genuine partial
requests are treated as HTMX.

## Reads: partial rendering

When an HTMX request hits an action listed in `htmx_partials`, velcro renders
**only** that named partial instead of the full template.

- **List** → the `table` partial (the `<table>` + pagination). Velcro also sets
  `HX-Push-Url` to the current URL so the address bar stays honest as the user
  searches, sorts, filters, or pages.
- **Create / Update** (`GET`) → the `form` partial.

```html
<!-- A live-filtering list: type and the table swaps, URL updates -->
<input
  type="search" name="q"
  hx-get="{% url 'lead-list' %}"
  hx-target="#lead-table"
  hx-trigger="keyup changed delay:300ms"
  hx-push-url="true">

<div id="lead-table">
  {% include "velcro/object_list.html" %}  {# server returns just the #table partial #}
</div>
```

Partials resolve through the **same template discovery chain** as full
templates. So if you override `crm/lead_list.html` but don't define a `table`
partial, an HTMX request falls back to the bundled template's `table` partial —
overriding markup never breaks HTMX. See
[Templates](../customisations/templates.md#partials-htmx-swap-targets).

## Writes: the `204` + event protocol

When `htmx_events` is on (the default), a successful HTMX **mutation** (create,
update, delete) does **not** redirect. Instead it returns:

```text
HTTP/1.1 204 No Content
HX-Trigger: {"leadChanged": {"action": "create", "pk": 7}}
```

The event name is `{model_name}Changed`; the payload carries the `action` and
the `pk`. Any element can listen and refresh itself precisely:

```html
<div
  hx-get="{% url 'lead-list' %}"
  hx-trigger="leadChanged from:body"
  hx-target="this">
  {% include "velcro/object_list.html" %}
</div>
```

**Outcome** — submit the create form (e.g. in a modal); the server replies `204`
with the event; the list elsewhere on the page hears `leadChanged` and reloads
its own `table` partial. The success message is still flashed for the next
render.

### Invalid submissions

An invalid `POST` re-renders the `form` partial with errors in place (status
`200`), so validation errors appear without a full page reload — no special
handling needed.

## Customising the HTMX behaviour

### Change which partial an action returns

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    htmx_partials = {
        "list": "table",
        "create": "form",
        "update": "form",
        "detail": "card",     # add a 'card' partial to your detail template
    }
```

### Turn off the event protocol

Set `htmx_events = False` to make HTMX mutations redirect like normal requests
(useful if you'd rather swap in the new page than emit an event):

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status"]
    htmx_events = False
```

### Rename the event

```python
def get_htmx_event_name(self):
    return "salesDataChanged"
```

### Swap-based mutations

To return rendered HTML for the client to swap in (instead of a `204`), override
`htmx_success_response()`:

```python
def htmx_success_response(self):
    # e.g. render the updated row and let htmx swap it into the table
    return self.render_to_response(self.get_context_data())
```

## Progressive enhancement

Because everything is driven by request headers, the same endpoints serve a
fully working non-JS experience: a normal `POST` redirects, a normal `GET`
returns the full page. Add htmx attributes to enhance; remove them and nothing
breaks.

## Related

- [Templates](../customisations/templates.md) — partials and the discovery fallback
- [Forms](forms.md) — inline validation errors
- [Messages and redirects](messages-and-redirects.md) — the non-HTMX fallback