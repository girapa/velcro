# Quickstart

This page takes a single model from nothing to a full set of working CRUD
views. It uses the `Lead` model from the [CRM example](crm-example.md).

## 1. Define a view

```python
# crm/views.py
from velcro import CRUDView
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status"]
```

Two attributes — `model` and `fields` — are all velcro needs. `fields` drives
both the list table columns and the create/update forms (each is independently
overridable; see [Forms](guides/forms.md) and
[Fields and value rendering](guides/fields-and-rendering.md)).

## 2. Mount the URLs

```python
# crm/urls.py
from .views import LeadCRUD

urlpatterns = [*LeadCRUD.get_urls()]
```

`get_urls()` returns a list of URL patterns — add it into `urlpatterns`.

## 3. That's it

You now have five routed, named views:

```text
/lead/                  lead-list      list every lead
/lead/new/              lead-create    create form
/lead/<int:pk>/         lead-detail    one lead
/lead/<int:pk>/edit/    lead-update    update form
/lead/<int:pk>/delete/  lead-delete    delete confirmation
```

Each renders with a bundled, framework-agnostic template, flashes a success
message on create/update/delete, and redirects sensibly afterwards (to the
object's detail page, or back to the list after deletion).

## Going further

A real view rarely stops at the two-attribute version. Each addition below is
covered in depth in its own guide:

```python
from velcro import CRUDView
from .models import Lead
from .forms import LeadCreateForm


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]

    # List columns differ from form fields.
    list_fields = ["company_name", "status", "owner"]            # guides/fields-and-rendering.md

    # A bespoke form for creation only.
    create_form_class = LeadCreateForm                           # guides/forms.md

    # Search box, sortable columns, filter form.
    search_fields = ["company_name", "contact_name", "email"]    # guides/search-ordering-filtering.md
    ordering_fields = ["company_name", "created_at", "status"]
    filterset_fields = ["status", "owner"]

    # Page the list.
    paginate_by = 25                                             # guides/pagination.md

    # Lock it down.
    login_required = True                                        # customisations/access-control.md
    permissions = "model"

    # Restrict the queryset to the current user.
    def get_queryset(self):                                      # guides/querysets.md
        return super().get_queryset().filter(owner=self.request.user)
```

For operations beyond CRUD (qualify a lead, convert it to an account), see
[Custom actions](customisations/custom-actions.md). For the complete map of
everything you can change, see the
[Customisation overview](customisations/overview.md).