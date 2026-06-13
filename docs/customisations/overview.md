# Customisation overview

Velcro is designed to be customised by **setting class attributes** or
**overriding methods** on `CRUDView`. Reach for an attribute first; drop to a
method only when the behaviour depends on the request or the object.

Most attributes participate in the per-action resolution chain.

## Per-action setting convention

Velcro resolves most settings like this:

```text
{action}_{name}  ->  {name}  ->  default
```

For example:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
    list_fields = ["company_name", "status"]
    update_fields = ["company_name", "contact_name", "email", "status", "notes"]
```

- The `list` action uses `list_fields`.
- The `update` action uses `update_fields`.
- Other actions fall back to `fields`.

This works for any custom action too: an action named `qualify` looks up
`qualify_template_name`, `qualify_success_message`, and so on before falling
back to the general attribute.

## What can be customised?

| Area           | Attributes                                                                                           | Methods                                                                  | Guide |
|----------------|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|-------|
| Model/queryset | `model`, `queryset`                                                                                  | `get_queryset()`, `get_object()`                                         | [Querysets](../guides/querysets.md) |
| Fields         | `fields`, `{action}_fields`                                                                          | `get_fields()`                                                           | [Fields & rendering](../guides/fields-and-rendering.md) |
| Forms          | `form_class`, `{action}_form_class`                                                                  | `get_form_class()`, `get_form()`, `form_valid()`, `form_invalid()`       | [Forms](../guides/forms.md) |
| Templates      | `template_name`, `{action}_template_name`, `template_dir`, `template_name_suffix`, `base_template_name` | `get_template_names()`, `render_to_response()`                        | [Templates](templates.md) |
| Context        | `context_object_name`                                                                                | `get_context_data()`, `get_{action}_context_data()`                      | [Context hooks](../guides/context-hooks.md) |
| URLs           | `url_base`, `url_name_prefix`, `lookup_field`, `lookup_url_kwarg`, `path_converter`, `url_namespace` | `get_urls()`, `reverse()`, `maybe_reverse()`                             | [URLs & namespaces](../guides/urls-and-namespaces.md) |
| Search         | `search_fields`, `search_param`                                                                      | `get_search_query()`, `apply_search()`                                   | [Search/order/filter](../guides/search-ordering-filtering.md) |
| Ordering       | `ordering_fields`, `ordering_param`                                                                  | `get_current_ordering()`, `apply_ordering()`                             | [Search/order/filter](../guides/search-ordering-filtering.md) |
| Filtering      | `filterset_class`, `filterset_fields`                                                                | `get_filterset_class()`, `get_filterset()`                               | [Search/order/filter](../guides/search-ordering-filtering.md) |
| Pagination     | `paginate_by`, `page_kwarg`, `allow_empty`                                                           | `get_paginate_by()`, `get_paginator()`, `paginate_queryset()`            | [Pagination](../guides/pagination.md) |
| Permissions    | `login_required`, `permissions`                                                                      | `get_required_permission()`, `has_permission()`                          | [Access control](access-control.md) |
| Messages       | `success_message`, `{action}_success_message`                                                        | `get_success_message()`, `send_success_message()`                        | [Messages & redirects](../guides/messages-and-redirects.md) |
| Redirects      | `success_url`, `{action}_success_url`, `redirect_param`                                              | `get_success_url()`                                                      | [Messages & redirects](../guides/messages-and-redirects.md) |
| HTMX           | `htmx_partials`, `htmx_events`                                                                       | `is_htmx`, `get_htmx_partial()`, `get_htmx_event_name()`, `htmx_success_response()` | [HTMX](../guides/htmx.md) |
| Actions        | `extra_actions`                                                                                      | `get_actions()`, `@action`-decorated methods                            | [Custom actions](custom-actions.md) |

For the exhaustive list of names see the [API tree](../references/api-tree.md);
for every default value see [Defaults](../references/defaults.md).

## Prefer small overrides

Velcro is designed so most changes need only a class attribute.

**Start with attributes** for static configuration:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email"]
    search_fields = ["company_name", "email"]
```

**Use a method** when behaviour depends on the request:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email"]

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)
```

**Use a model method or service** when the action carries business logic — keep
the view thin:

```python
class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email"]

    @action(detail=True, methods=["post"], permission="change")
    def qualify(self, request, *args, **kwargs):
        self.object = self.get_object()
        qualify_lead(lead=self.object, actor=request.user)  # service function
        return HttpResponseRedirect(self.reverse("detail", self.object))
```

Velcro replaces the wiring, not your architecture: fat models / thin views,
services, and selectors all still apply.