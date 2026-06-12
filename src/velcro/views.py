"""
velcro's core: a single CRUDView dispatching to Actions.

Design notes
------------
* One view class serves every action. ``as_view(action=...)`` binds the
  action's HTTP handlers onto the instance, exactly one mental model.
* Every piece of per-action configuration resolves through one chain,
  implemented by ``_resolve()``:

      self.{action}_{name}  ->  self.{name}  ->  default

  So ``list_fields`` falls back to ``fields``, ``update_form_class`` to
  ``form_class``, ``detail_template_name`` to ``template_name``, and so on.
  Learn the convention once, apply it everywhere.
* Per-action context hooks: define ``get_{action}_context_data(context)``
  and it is called after the base ``get_context_data``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib import messages
from django.contrib.auth import get_permission_codename
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.paginator import InvalidPage, Page, Paginator
from django.db.models import Model, Q, QuerySet
from django.forms import models as model_forms
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, URLPattern, path, reverse
from django.utils.decorators import classonlymethod
from django.utils.functional import classproperty
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import View

from . import renderers
from .actions import (
    DEFAULT_ACTIONS,
    LOOKUP,
    Action,
    collect_decorated_actions,
)

_UNSET = object()


def _filterset_factory():
    """Soft import: django-filter is only required if filtering is configured."""
    try:
        from django_filters.filterset import filterset_factory
    except ImportError as exc:
        raise ImproperlyConfigured(
            "Using 'filterset_fields' or 'filterset_class' requires "
            "django-filter. Install it with: pip install velcro[filter]"
        ) from exc
    return filterset_factory


class CRUDView(View):
    """List, detail, create, update, delete — plus your own actions —
    for a model, in one class."""

    # Set per-request by as_view().
    action: Action

    model: ClassVar[type[Model] | None] = None
    fields: ClassVar[list[str] | None] = None

    # Object lookup. lookup_url_kwarg defaults to lookup_field.
    lookup_field: ClassVar[str] = "pk"
    lookup_url_kwarg: ClassVar[str | None] = None
    path_converter: ClassVar[str] = "int"

    # Explicit URL namespace for reversing. If None, the namespace is read
    # from request.resolver_match at request time — so the same view class
    # works bare, under include(..., namespace="staff"), or mounted twice
    # under different namespaces, with zero configuration.
    url_namespace: ClassVar[str | None] = None

    # Optional config; each participates in the per-action resolution chain.
    queryset: ClassVar[QuerySet | None] = None
    form_class: ClassVar[type | None] = None
    template_name: ClassVar[str | None] = None
    success_url: ClassVar[str | None] = None
    context_object_name: ClassVar[str | None] = None

    # Template discovery. template_dir overrides the model's app_label
    # (Neapolitan issue #63: CRUD views living in a different app than
    # their models).
    template_dir: ClassVar[str | None] = None
    template_name_suffix: str | None = None

    # Base template the default templates extend; must define a "content"
    # block. Exposed in context as base_template_name.
    base_template_name: ClassVar[str] = "base.html"

    # Pagination.
    paginate_by: ClassVar[int | None] = None
    page_kwarg: ClassVar[str] = "page"
    allow_empty: ClassVar[bool] = True

    # Search (no dependency). Fields support admin-style prefixes:
    # "^name" istartswith, "=name" iexact, plain name icontains.
    search_fields: ClassVar[list[str] | None] = None
    search_param: ClassVar[str] = "q"

    # Ordering (no dependency). ?ordering=-due,title — validated against
    # this whitelist; unknown fields are silently dropped.
    ordering_fields: ClassVar[list[str] | None] = None
    ordering_param: ClassVar[str] = "ordering"

    # Filtering via django-filter (optional dependency: velcro[filter]).
    filterset_class: ClassVar[type | None] = None
    filterset_fields: ClassVar[list[str] | None] = None

    # HTMX (no dependency; pure header/partial protocol).
    # Maps action name -> template partial served when the request carries
    # HX-Request (hx-boosted requests get the full page). Partials resolve
    # through the same template candidate chain, so an app override without
    # the partial falls back to the bundled template's partial.
    htmx_partials: ClassVar[dict[str, str]] = {
        "list": "table",
        "create": "form",
        "update": "form",
    }
    # On successful HTMX mutations: respond 204 + HX-Trigger event
    # ("{model}Changed") instead of a redirect. Set False to redirect as
    # usual. Override htmx_success_response() for swap-based patterns.
    htmx_events: ClassVar[bool] = True

    # Access control.
    # login_required: anonymous users are redirected to settings.LOGIN_URL.
    # permissions: None disables checks; "model" maps each action's
    # permission shorthand ("view"/"add"/"change"/"delete") to the model's
    # standard permissions; a dict overrides per action name, with missing
    # keys falling back to the shorthand. A failed check raises
    # PermissionDenied (403) — authenticated or not.
    login_required: ClassVar[bool] = False
    permissions: ClassVar[str | dict[str, str | None] | None] = None

    # Messages. None = sensible default ("Bookmark created."); "" disables.
    # Supports {object} and {verbose_name} placeholders, and participates
    # in the per-action chain ({action}_success_message).
    success_message: ClassVar[str | None] = None

    # Name of the query/POST parameter allowed to override the success URL
    # (validated against the request host). None disables.
    redirect_param: ClassVar[str | None] = "next"

    object: Model | None = None
    object_list: QuerySet | None = None

    # Extra Action instances beyond the defaults and @action-decorated
    # methods. Set to a list to add; override get_actions() for full control.
    extra_actions: ClassVar[list[Action] | None] = None

    # ------------------------------------------------------------------
    # Config resolution
    # ------------------------------------------------------------------

    def _resolve(self, name: str, default: Any = _UNSET) -> Any:
        """Resolve ``{action}_{name}`` -> ``{name}`` -> default."""
        value = getattr(self, f"{self.action.name}_{name}", None)
        if value is None:
            value = getattr(self, name, None)
        if value is None and default is not _UNSET:
            return default
        return value

    def get_fields(self) -> list[str]:
        fields = self._resolve("fields")
        if fields is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} requires 'fields' (or "
                f"'{self.action.name}_fields'), or an explicit form_class "
                "for form actions."
            )
        return fields

    # ------------------------------------------------------------------
    # Queryset and object lookup
    # ------------------------------------------------------------------

    def get_queryset(self) -> QuerySet:
        """Base queryset: list of objects, or lookup source for detail
        actions."""
        if self.queryset is not None:
            return self.queryset._clone()
        if self.model is not None:
            return self.model._default_manager.all()
        raise ImproperlyConfigured(
            f"{self.__class__.__name__} must define 'queryset' or 'model', or override get_queryset()."
        )

    def get_object(self) -> Model:
        queryset = self.get_queryset()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        try:
            lookup = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        except KeyError as err:
            raise ImproperlyConfigured(
                f"Lookup field '{lookup_url_kwarg}' was not provided in view kwargs to {self.__class__.__name__}."
            ) from err
        obj = get_object_or_404(queryset, **lookup)
        if self.get_required_permission() is not None and not self.has_permission(obj=obj):
            raise PermissionDenied(f"Permission denied for action '{self.action.name}' on this object.")
        return obj

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if self.login_required and not request.user.is_authenticated:
            # Imported lazily: django.contrib.auth.views pulls in models,
            # which must not happen at module import time (the velcro app
            # may be loading inside the app registry).
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if self.get_required_permission() is not None and not self.has_permission():
            raise PermissionDenied(f"Permission denied for action '{self.action.name}'.")
        return super().dispatch(request, *args, **kwargs)

    def _expand_permission(self, perm: str | None) -> str | None:
        """Expand "view"/"add"/"change"/"delete" shorthands to the model's
        standard permission string; full "app_label.codename" strings pass
        through untouched."""
        if perm is None or "." in perm:
            return perm
        if self.model is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} cannot expand permission shorthand {perm!r} without a 'model'."
            )
        meta = self.model._meta
        return f"{meta.app_label}.{get_permission_codename(perm, meta)}"

    def get_required_permission(self) -> str | None:
        """The permission string required for the current action, or None."""
        if self.permissions is None:
            return None
        if isinstance(self.permissions, dict) and self.action.name in self.permissions:
            return self._expand_permission(self.permissions[self.action.name])
        return self._expand_permission(self.action.permission)

    def has_permission(self, obj: Model | None = None) -> bool:
        """Does the current user hold the required permission?

        With an ``obj``, the object-level check is tried first and falls
        back to the model-level check — so django-guardian/django-rules
        backends grant per-object access, while the default backend
        behaves as plain model permissions. Override for custom logic.
        """
        perm = self.get_required_permission()
        if perm is None:
            return True
        user = self.request.user
        if obj is not None and user.has_perm(perm, obj):
            return True
        return user.has_perm(perm)

    # ------------------------------------------------------------------
    # Standard handlers
    # ------------------------------------------------------------------

    def list(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """GET handler for the list action.

        Queryset pipeline: get_queryset -> filterset -> search -> ordering
        -> pagination. Search composes on top of the filterset (AND), and
        ordering applies last.
        """
        queryset = self.get_queryset()
        filterset = self.get_filterset(queryset)
        if filterset is not None:
            queryset = filterset.qs
        queryset = self.apply_search(queryset)
        queryset = self.apply_ordering(queryset)

        if not self.allow_empty and not queryset.exists():
            raise Http404(_("Empty list and 'allow_empty' is False."))

        extra = {
            "filterset": filterset,
            "search_enabled": bool(self._resolve("search_fields")),
            "search_param": self.search_param,
            "search_query": self.get_search_query(),
        }
        paginate_by = self.get_paginate_by()
        if paginate_by is None:
            self.object_list = queryset
            context = self.get_context_data(page_obj=None, is_paginated=False, paginator=None, **extra)
        else:
            page = self.paginate_queryset(queryset, paginate_by)
            self.object_list = page.object_list
            context = self.get_context_data(
                page_obj=page,
                is_paginated=page.has_other_pages(),
                paginator=page.paginator,
                **extra,
            )
        return self.render_to_response(context)

    # ------------------------------------------------------------------
    # Search, ordering, filtering
    # ------------------------------------------------------------------

    def get_search_query(self) -> str:
        request = getattr(self, "request", None)
        if request is None:
            return ""
        return request.GET.get(self.search_param, "").strip()

    @staticmethod
    def _search_lookup(field: str) -> str:
        if field.startswith("^"):
            return f"{field[1:]}__istartswith"
        if field.startswith("="):
            return f"{field[1:]}__iexact"
        return f"{field}__icontains"

    def apply_search(self, queryset: QuerySet) -> QuerySet:
        fields = self._resolve("search_fields")
        query = self.get_search_query()
        if not fields or not query:
            return queryset
        condition = Q()
        for field in fields:
            condition |= Q(**{self._search_lookup(field): query})
        queryset = queryset.filter(condition)
        # Relation-spanning searches can produce duplicate rows.
        if any("__" in field.lstrip("^=") for field in fields):
            queryset = queryset.distinct()
        return queryset

    def get_current_ordering(self) -> list[str]:
        """Validated ordering from the request, e.g. ["-due", "title"]."""
        allowed = set(self._resolve("ordering_fields") or [])
        request = getattr(self, "request", None)
        if not allowed or request is None:
            return []
        raw = request.GET.get(self.ordering_param, "")
        return [part.strip() for part in raw.split(",") if part.strip() and part.strip().lstrip("-") in allowed]

    def apply_ordering(self, queryset: QuerySet) -> QuerySet:
        if ordering := self.get_current_ordering():
            return queryset.order_by(*ordering)
        return queryset

    def get_filterset_class(self) -> type | None:
        filterset_class = self._resolve("filterset_class")
        filterset_fields = self._resolve("filterset_fields")
        if filterset_class is None and filterset_fields is None:
            return None
        factory = _filterset_factory()
        if filterset_class is not None:
            return filterset_class
        return factory(self.model, fields=filterset_fields)

    def get_filterset(self, queryset: QuerySet):
        filterset_class = self.get_filterset_class()
        if filterset_class is None:
            return None
        return filterset_class(self.request.GET, queryset=queryset, request=self.request)

    def detail(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """GET handler for the detail action."""
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def show_form(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """GET handler for create/update form actions."""
        if self.action.detail:
            self.object = self.get_object()
        form = self.get_form(instance=self.object)
        return self.render_to_response(self.get_context_data(form=form))

    def process_form(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """POST handler for create/update form actions."""
        if self.action.detail:
            self.object = self.get_object()
        form = self.get_form(data=request.POST, files=request.FILES, instance=self.object)
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def confirm_delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """GET handler for the delete confirmation page."""
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def process_deletion(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """POST handler performing the deletion."""
        self.object = self.get_object()
        deleted_pk = self.object.pk
        self.object.delete()
        # Django nulls the pk on delete; restore it so messages and the
        # HTMX event can still identify which object was removed.
        self.object.pk = deleted_pk
        self.send_success_message()
        if self.is_htmx and self.htmx_events:
            return self.htmx_success_response()
        return HttpResponseRedirect(self.get_success_url())

    # ------------------------------------------------------------------
    # Forms (success-URL reversing arrives with URL generation)
    # ------------------------------------------------------------------

    def get_form_class(self) -> type:
        form_class = self._resolve("form_class")
        if form_class is not None:
            return form_class
        if self.model is not None and self._resolve("fields") is not None:
            return model_forms.modelform_factory(self.model, fields=self.get_fields())
        raise ImproperlyConfigured(
            f"{self.__class__.__name__} must define 'form_class' or both "
            "'model' and 'fields', or override get_form_class()."
        )

    def get_form(self, data=None, files=None, **kwargs: Any):
        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)

    def form_valid(self, form) -> HttpResponse:
        self.object = form.save()
        self.send_success_message()
        if self.is_htmx and self.htmx_events:
            return self.htmx_success_response()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form) -> HttpResponse:
        return self.render_to_response(self.get_context_data(form=form))

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    DEFAULT_MESSAGE_VERBS: ClassVar[dict[str, Any]] = {
        "create": gettext_lazy("created"),
        "update": gettext_lazy("updated"),
        "delete": gettext_lazy("deleted"),
    }

    def get_success_message(self) -> str | None:
        """Message flashed after a successful mutation.

        Resolution: ``{action}_success_message`` -> ``success_message`` ->
        a default for create/update/delete ("Bookmark created."). Set to
        ``""`` to disable. Supports {object} and {verbose_name}.
        """
        message = self._resolve("success_message")
        if message is None:
            verb = self.DEFAULT_MESSAGE_VERBS.get(self.action.name)
            if verb is None or self.model is None:
                return None
            return f"{capfirst(self.model._meta.verbose_name)} {verb}."
        if message == "":
            return None
        verbose_name = self.model._meta.verbose_name if self.model else ""
        return message.format(object=self.object, verbose_name=verbose_name)

    def send_success_message(self) -> None:
        if message := self.get_success_message():
            # fail_silently: no-op when the messages framework isn't installed.
            messages.success(self.request, message, fail_silently=True)

    def get_success_url(self) -> str:
        """Where to go after a successful mutation.

        Resolution: a safe ``?next=`` value -> ``{action}_success_url`` ->
        ``success_url`` -> default policy (detail page of the saved object;
        list page after deletion).
        """
        if self.redirect_param:
            candidate = self.request.POST.get(self.redirect_param) or self.request.GET.get(self.redirect_param)
            if candidate and url_has_allowed_host_and_scheme(
                candidate,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
            ):
                return candidate
        url = self._resolve("success_url")
        if url is not None:
            return str(url)
        if self.action.name != "delete" and self.object is not None:
            detail_url = self.maybe_reverse("detail", self.object)
            if detail_url is not None:
                return detail_url
        list_url = self.maybe_reverse("list")
        if list_url is not None:
            return list_url
        raise ImproperlyConfigured(
            f"{self.__class__.__name__} could not determine a success URL "
            f"for action '{self.action.name}': no 'success_url' is set and "
            "neither the detail nor list URL could be reversed. Define "
            f"'success_url' or '{self.action.name}_success_url', or "
            "override get_success_url()."
        )

    # ------------------------------------------------------------------
    # Reversing
    # ------------------------------------------------------------------

    def _action_by_name(self, name: str) -> Action:
        for act in type(self).get_actions():
            if act.name == name:
                return act
        raise KeyError(name)

    def _namespace(self) -> str:
        if self.url_namespace is not None:
            return self.url_namespace
        request = getattr(self, "request", None)
        if request is not None and request.resolver_match is not None:
            return request.resolver_match.namespace or ""
        return ""

    def reverse(self, action: Action | str, obj: Model | None = None) -> str:
        """Reverse the URL for one of this view's actions, automatically
        applying the namespace the view is mounted under (Neapolitan
        issue #16: namespaced urlpatterns)."""
        act = action if isinstance(action, Action) else self._action_by_name(action)
        url_name = f"{self.url_name_prefix}-{act.name}"
        if namespace := self._namespace():
            url_name = f"{namespace}:{url_name}"
        if act.detail:
            target = obj if obj is not None else self.object
            url_kwarg = self.lookup_url_kwarg or self.lookup_field
            return reverse(url_name, kwargs={url_kwarg: getattr(target, self.lookup_field)})
        return reverse(url_name)

    def maybe_reverse(self, action: Action | str, obj: Model | None = None) -> str | None:
        """Like reverse(), but returns None when the action isn't routed."""
        try:
            return self.reverse(action, obj)
        except NoReverseMatch, KeyError:
            return None

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def get_paginate_by(self) -> int | None:
        return self._resolve("paginate_by")

    def get_paginator(self, queryset: QuerySet, page_size: int) -> Paginator:
        return Paginator(queryset, page_size)

    def paginate_queryset(self, queryset: QuerySet, page_size: int) -> Page:
        paginator = self.get_paginator(queryset, page_size)
        page_number = self.kwargs.get(self.page_kwarg) or self.request.GET.get(self.page_kwarg) or 1
        try:
            page_number = int(page_number)
        except ValueError as err:
            if page_number == "last":
                page_number = paginator.num_pages
            else:
                raise Http404(_("Page is not 'last', nor can it be converted to an int.")) from err
        try:
            return paginator.page(page_number)
        except InvalidPage as exc:
            raise Http404(_("Invalid page (%(page)s): %(error)s") % {"page": page_number, "error": str(exc)}) from exc

    # ------------------------------------------------------------------
    # Context and rendering
    # ------------------------------------------------------------------

    def get_context_object_name(self, is_list: bool = False) -> str | None:
        if self.context_object_name is not None:
            return self.context_object_name
        if self.model is not None:
            name = self.model._meta.object_name.lower()
            return f"{name}_list" if is_list else name
        return None

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["view"] = self
        kwargs["action"] = self.action.name
        kwargs["base_template_name"] = self.base_template_name
        if self.model is not None:
            kwargs["object_verbose_name"] = self.model._meta.verbose_name
            kwargs["object_verbose_name_plural"] = self.model._meta.verbose_name_plural

        kwargs["list_view_url"] = self.maybe_reverse("list")
        kwargs["create_view_url"] = self.maybe_reverse("create")

        try:
            display_fields = self.get_fields() if self.model else None
        except ImproperlyConfigured:
            display_fields = None

        if self.object is not None:
            kwargs["object"] = self.object
            kwargs["detail_view_url"] = self.maybe_reverse("detail", self.object)
            kwargs["update_view_url"] = self.maybe_reverse("update", self.object)
            kwargs["delete_view_url"] = self.maybe_reverse("delete", self.object)
            if display_fields:
                kwargs["object_fields"] = [renderers.resolve_cell(self, self.object, name) for name in display_fields]
            if name := self.get_context_object_name():
                kwargs[name] = self.object
        if self.object_list is not None:
            kwargs["object_list"] = self.object_list
            if display_fields:
                kwargs["object_table"] = {
                    "headers": self._build_headers(display_fields),
                    "rows": renderers.build_rows(self, self.object_list, display_fields),
                }
            if name := self.get_context_object_name(is_list=True):
                kwargs[name] = self.object_list

        # Per-action hook: get_list_context_data, get_archive_context_data...
        hook = getattr(self, f"get_{self.action.name}_context_data", None)
        if hook is not None:
            kwargs = hook(kwargs)
        return kwargs

    def _build_headers(self, display_fields: list[str]) -> list[dict[str, str | None]]:
        """Header cells for the list table. Sortable columns carry the
        ordering value their link should set (toggling asc/desc) and the
        current direction for an indicator."""
        allowed = set(self._resolve("ordering_fields") or [])
        current = self.get_current_ordering()
        headers = []
        labels = renderers.build_headers(self, display_fields)
        for name, label in zip(display_fields, labels, strict=True):
            ordering: str | None = None
            direction = ""
            if name in allowed:
                if name in current:
                    ordering, direction = f"-{name}", "asc"
                elif f"-{name}" in current:
                    ordering, direction = name, "desc"
                else:
                    ordering = name
            headers.append({"label": label, "ordering": ordering, "direction": direction})
        return headers

    def get_template_names(self) -> list[str]:
        if (template_name := self._resolve("template_name")) is not None:
            return [template_name]
        if self.model is not None and self.template_name_suffix is not None:
            prefix = self.template_dir or self.model._meta.app_label
            name = self.model._meta.object_name.lower()
            return [
                f"{prefix}/{name}{self.template_name_suffix}.html",
                f"velcro/object{self.template_name_suffix}.html",
            ]
        raise ImproperlyConfigured(
            f"{self.__class__.__name__} must define 'template_name', or "
            "'model' with an action that has a template_suffix, or override "
            "get_template_names()."
        )

    def render_to_response(self, context: dict[str, Any]) -> HttpResponse:
        templates = self.get_template_names()
        headers: dict[str, str] = {}
        if (partial := self.get_htmx_partial()) is not None:
            templates = [f"{name}#{partial}" for name in templates]
            if self.action.name == "list" and self.request.method == "GET":
                headers["HX-Push-Url"] = self.request.get_full_path()
        response = TemplateResponse(
            request=self.request,
            template=templates,
            context=context,
        )
        for key, value in headers.items():
            response.headers[key] = value
        return response

    # ------------------------------------------------------------------
    # HTMX
    # ------------------------------------------------------------------

    @property
    def is_htmx(self) -> bool:
        """True for genuine HTMX partial requests (hx-boosted navigation
        wants the full page and is excluded)."""
        headers = self.request.headers
        return headers.get("HX-Request") == "true" and headers.get("HX-Boosted") != "true"

    def get_htmx_partial(self) -> str | None:
        if not self.is_htmx:
            return None
        return self.htmx_partials.get(self.action.name)

    def get_htmx_event_name(self) -> str:
        assert self.model is not None
        return f"{self.model._meta.model_name}Changed"

    def htmx_success_response(self) -> HttpResponse:
        """Response for a successful HTMX mutation: 204 + HX-Trigger.

        The event payload carries the action and pk so listeners can
        refresh precisely: hx-trigger="bookmarkChanged from:body".
        Override to return a rendered partial for swap-based patterns.
        """
        import json

        payload = {
            self.get_htmx_event_name(): {
                "action": self.action.name,
                "pk": self.object.pk if self.object and self.object.pk else None,
            }
        }
        return HttpResponse(status=204, headers={"HX-Trigger": json.dumps(payload)})

    # ------------------------------------------------------------------
    # URL generation
    # ------------------------------------------------------------------

    @classproperty
    def url_base(cls) -> str:  # noqa: N805
        """Base path component of generated URLs. Defaults to the model
        name; override by setting ``url_base`` on the class."""
        if cls.model is None:
            raise ImproperlyConfigured(
                f"{cls.__name__} must define 'model' or set 'url_base' explicitly to generate URLs."
            )
        return cls.model._meta.model_name

    @classproperty
    def url_name_prefix(cls) -> str:  # noqa: N805
        """Prefix for generated URL *names*. Defaults to url_base, but is
        independently overridable (Neapolitan issue #67) so two views can
        share a path shape with distinct reverse names, or vice versa."""
        return cls.url_base

    @classonlymethod
    def _lookup_fragment(cls) -> str:
        url_kwarg = cls.lookup_url_kwarg or cls.lookup_field
        return f"<{cls.path_converter}:{url_kwarg}>"

    @classonlymethod
    def _url_for(cls, act: Action) -> URLPattern:
        fragment = act.url_pattern.format(lookup=cls._lookup_fragment())
        route = "/".join(part for part in (cls.url_base, fragment) if part) + "/"
        return path(
            route,
            cls.as_view(action=act),
            name=f"{cls.url_name_prefix}-{act.name}",
        )

    @classonlymethod
    def get_urls(cls, actions: list[Action | str] | None = None) -> list[URLPattern]:
        """Generate URL patterns for this view's actions.

        ``actions`` may be Action instances or names::

            urlpatterns = [*BookmarkView.get_urls()]
            urlpatterns = [*BookmarkView.get_urls(["list", "detail"])]

        Static patterns are emitted before lookup patterns so that, with
        permissive converters like ``slug`` or ``str``, ``bookmark/new/``
        is never shadowed by ``bookmark/<slug:pk>/``.
        """
        available = {a.name: a for a in cls.get_actions()}
        if actions is None:
            selected = list(available.values())
        else:
            selected = []
            for entry in actions:
                if isinstance(entry, Action):
                    selected.append(entry)
                else:
                    try:
                        selected.append(available[entry])
                    except KeyError as err:
                        raise ImproperlyConfigured(
                            f"{cls.__name__} has no action named {entry!r}. Available: {sorted(available)}."
                        ) from err
        # Stable sort: patterns without a lookup first.
        selected.sort(key=lambda a: LOOKUP in a.url_pattern)
        return [cls._url_for(act) for act in selected]

    # ------------------------------------------------------------------
    # Action registry and as_view
    # ------------------------------------------------------------------

    @classonlymethod
    def get_actions(cls) -> list[Action]:
        """All actions this view serves: defaults, extra_actions, and
        @action-decorated methods. Later names override earlier ones, so a
        decorated 'list' replaces the default."""
        registry: dict[str, Action] = {a.name: a for a in DEFAULT_ACTIONS}
        for act in cls.extra_actions or []:
            registry[act.name] = act
        for act in collect_decorated_actions(cls):
            registry[act.name] = act
        return list(registry.values())

    @classonlymethod
    def as_view(cls, action: Action, **initkwargs: Any):  # type: ignore[override]
        """Entry point: returns a callable serving the given action."""
        handler_names = {h for a in cls.get_actions() for h in a.handlers.values()}
        for key in initkwargs:
            if key in cls.http_method_names or key in handler_names:
                raise TypeError(
                    f"{key!r} is a handler/method name and cannot be passed "
                    f"as a keyword argument to {cls.__name__}.as_view()."
                )
            if not hasattr(cls, key):
                raise TypeError(
                    f"{cls.__name__}.as_view() received an invalid keyword "
                    f"{key!r}. as_view only accepts arguments that are "
                    "already attributes of the class."
                )

        def view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            self = cls(**initkwargs)
            self.action = action
            if self.template_name_suffix is None:
                self.template_name_suffix = action.template_suffix
            self.setup(request, *args, **kwargs)
            if not hasattr(self, "request"):
                raise AttributeError(
                    f"{cls.__name__} instance has no 'request' attribute. "
                    "Did you override setup() and forget to call super()?"
                )
            for method, handler_name in action.handlers.items():
                setattr(self, method, getattr(self, handler_name))
            return self.dispatch(request, *args, **kwargs)

        view.view_class = cls  # type: ignore[attr-defined]
        view.view_initkwargs = initkwargs  # type: ignore[attr-defined]
        view.action = action  # type: ignore[attr-defined]
        view.__doc__ = cls.__doc__
        view.__module__ = cls.__module__
        view.__dict__.update(cls.dispatch.__dict__)
        return view
