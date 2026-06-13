# Fields and value rendering

`fields` is the most-used attribute in velcro. It decides three things at once:

1. which **columns** appear in the list table,
2. which **rows** appear on the detail page,
3. which **inputs** appear in the generated create/update form.

Each is independently overridable through the resolution chain, and the *values*
are rendered admin-style by `velcro.renderers`.

## What can be customised

| Setting / method   | Default | Purpose                                              |
|--------------------|---------|------------------------------------------------------|
| `fields`           | `None`  | Field specs for table, detail, and forms             |
| `{action}_fields`  | `None`  | Field specs for one action (e.g. `list_fields`)      |
| `get_fields()`     | resolves `{action}_fields` → `fields` | Override for dynamic field sets |

A field spec is the same idea as the admin's `list_display`: it can be a **model
field name**, a **method on the model**, or a **method on the view**.

## The default

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]
```

**Outcome** — the list shows those five columns, the detail page shows those
five rows, and the create/update forms expose those five inputs.

If neither `fields` nor `{action}_fields` (nor a `form_class`, for form actions)
is set, velcro raises `ImproperlyConfigured`.

## Different fields per action

A common split — a compact list, a richer detail, a fuller edit form:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]
    list_fields = ["company_name", "status", "owner"]                       # table
    update_fields = ["company_name", "contact_name", "email", "status",
                     "owner", "notes"]                                      # edit form
```

Any action resolves `{action}_fields` first, then `fields`. So `create` and
`detail` above fall back to the five-field `fields`, while `list` and `update`
use their own.

## Computed columns

A field spec that isn't a model field can be a **method on the view**, called
with the object. Give it `short_description` to set the column header:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "status", "domain"]

    def domain(self, obj):
        return obj.email.split("@")[-1]
    domain.short_description = "Email domain"
```

It can also be a **method on the model** (called with no args). Resolution order
for a spec that is not a model field: view method (called with the object) →
object attribute, calling it if it's a method.

## How values are rendered

`velcro.renderers` turns each spec + object into a `Cell` (a `label`, a display
`value`, and an optional `url`). The rendering rules, matching the admin:

| Value                        | Rendered as                                          |
|------------------------------|------------------------------------------------------|
| `None` or empty string       | `—` (`renderers.EMPTY_VALUE`)                        |
| `True` / `False`             | `✓` / `✗`                                            |
| A field with `choices`       | its label, via `get_<field>_display()`               |
| A `ForeignKey` instance      | `str(obj)`, linked to its detail page when routed    |
| A many-to-many / reverse set | comma-separated `str()` of each related object       |
| dates, numbers, etc.         | localised via Django's formatting                    |

### Choice fields show labels

`status` on a `Lead` is a `TextChoices` field, so the list and detail show
`Qualified`, not `qualified` — velcro calls `get_status_display()` for you.

### ForeignKeys link automatically

A `ForeignKey` cell links to the related object's detail page **if one is
routed** under the current namespace, by the convention
`{related_model_name}-detail`. So an `owner` or `account` column becomes a
clickable link when (and only when) you've mounted a CRUD view for that model.
No route → plain text, no error.

```python
# If AccountCRUD.get_urls() is mounted, a Deal's `account` cell links to
# the account detail page automatically.
class DealCRUD(CRUDView):
    model = Deal
    fields = ["name", "account", "amount", "stage"]
```

## Column headers

The header label for a spec is resolved as: the model field's `verbose_name` →
the view/model attribute's `short_description` → the spec name with underscores
replaced by spaces. All are passed through `capfirst`.

## Sortable headers

When a column's spec is also listed in `ordering_fields`, its header becomes a
sort link with a ▲/▼ indicator. That is purely an ordering concern — see
[Search, ordering, filtering](search-ordering-filtering.md).

## In templates

Templates never compute values; they loop over prepared data:

- **Detail** — `object_fields` is a list of `Cell`:

  ```html
  {% for cell in object_fields %}
    <dt>{{ cell.label }}</dt>
    <dd>{% if cell.url %}<a href="{{ cell.url }}">{{ cell.value }}</a>
        {% else %}{{ cell.value }}{% endif %}</dd>
  {% endfor %}
  ```

- **List** — `object_table` is `{"headers": [...], "rows": [Row, ...]}`, where
  each `Row` carries `cells` plus `detail_url`, `update_url`, `delete_url`.

See [Templates](../customisations/templates.md) for overriding the markup.

## Dynamic field sets

For fields that depend on the request (e.g. show `notes` only to managers),
override `get_fields()`:

```python
def get_fields(self):
    fields = super().get_fields()
    if not self.request.user.has_perm("crm.view_lead_notes"):
        fields = [f for f in fields if f != "notes"]
    return fields
```

## Related

- [Forms](forms.md) — how `fields` becomes a modelform
- [Templates](../customisations/templates.md) — `Cell` / `Row` in markup
- [Search, ordering, filtering](search-ordering-filtering.md) — sortable columns