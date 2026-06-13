# CRM example domain

Every example in these docs uses one small CRM domain, defined here once. A CRM
is a good fit for velcro because each model needs standard CRUD plus a few
business-specific actions (qualify a lead, convert it, mark a deal won).

The domain models:

- **leads** — potential customers not yet qualified
- **accounts** — organisations you do business with
- **contacts** — people at an account
- **deals** — sales opportunities against an account
- **activities** — calls, emails, and tasks logged against the above

## Models

```python
# crm/models.py
from django.conf import settings
from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        DISQUALIFIED = "disqualified", "Disqualified"
        CONVERTED = "converted", "Converted"

    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leads",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.company_name


class Contact(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="contacts"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Deal(models.Model):
    class Stage(models.TextChoices):
        PROSPECT = "prospect", "Prospecting"
        PROPOSAL = "proposal", "Proposal sent"
        NEGOTIATION = "negotiation", "Negotiation"
        WON = "won", "Closed won"
        LOST = "lost", "Closed lost"

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="deals"
    )
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.PROSPECT
    )
    close_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="deals",
    )

    def __str__(self):
        return self.name


class Activity(models.Model):
    class Kind(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        TASK = "task", "Task"

    subject = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    due_date = models.DateField(null=True, blank=True)
    done = models.BooleanField(default=False)
    lead = models.ForeignKey(
        Lead, null=True, blank=True, on_delete=models.CASCADE, related_name="activities"
    )
    deal = models.ForeignKey(
        Deal, null=True, blank=True, on_delete=models.CASCADE, related_name="activities"
    )

    def __str__(self):
        return self.subject
```

## A basic CRUD view

```python
# crm/views.py
from velcro import CRUDView
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]
    search_fields = ["company_name", "contact_name", "email"]
    ordering_fields = ["company_name", "created_at", "status"]
    filterset_fields = ["status", "owner"]
```

```python
# crm/urls.py
from .views import LeadCRUD

urlpatterns = [*LeadCRUD.get_urls()]
```

### Generated URLs

```text
/lead/                  lead-list
/lead/new/              lead-create
/lead/<int:pk>/         lead-detail
/lead/<int:pk>/edit/    lead-update
/lead/<int:pk>/delete/  lead-delete
```

## Adding a CRM action

A real CRM needs more than CRUD. For example, a sales rep qualifies a lead — a
single-object `POST` that changes state and redirects. That is a
[custom action](customisations/custom-actions.md):

```python
from django.contrib import messages
from django.http import HttpResponseRedirect
from velcro import CRUDView, action
from .models import Lead


class LeadCRUD(CRUDView):
    model = Lead
    fields = ["company_name", "contact_name", "email", "status", "owner"]

    @action(detail=True, methods=["post"], permission="change")
    def qualify(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = Lead.Status.QUALIFIED
        self.object.save(update_fields=["status"])
        messages.success(request, f"{self.object} was qualified.")
        return HttpResponseRedirect(self.reverse("detail", self.object))
```

This adds one more route:

```text
POST /lead/<int:pk>/qualify/    lead-qualify
```

Real business logic belongs in a model method or a service function — the
action just wires the request to it. See
[Custom actions](customisations/custom-actions.md) for the full treatment.