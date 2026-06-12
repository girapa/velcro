"""
Field rendering for velcro's default templates.

Turns a field spec (model field name, model method, or view method — same
semantics as admin's ``list_display``) into display-ready cells:

* choices fields render their label via ``get_FOO_display()``,
* booleans render as ✓ / ✗,
* dates and numbers are localized,
* ForeignKey values link to the related model's detail view when one is
  routed under the current namespace (convention: ``{model_name}-detail``),
* many-to-many values render as a comma-separated list,
* view methods may set ``short_description`` for their column header.

The templates stay dumb: they only loop over ``Cell`` and ``Row`` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field, Model
from django.urls import NoReverseMatch, reverse
from django.utils import formats
from django.utils.text import capfirst

if TYPE_CHECKING:
    from .views import CRUDView

EMPTY_VALUE = "—"


@dataclass(frozen=True, slots=True)
class Cell:
    label: str
    value: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Row:
    object: Model
    cells: list[Cell]
    detail_url: str | None
    update_url: str | None
    delete_url: str | None


def _model_field(model: type[Model], name: str) -> Field | None:
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        return None


def field_label(view: CRUDView, model: type[Model], name: str) -> str:
    """Column/row header for a field spec."""
    field = _model_field(model, name)
    if field is not None and hasattr(field, "verbose_name"):
        return capfirst(str(field.verbose_name))
    attr = getattr(view, name, None) or getattr(model, name, None)
    if attr is not None and hasattr(attr, "short_description"):
        return capfirst(str(attr.short_description))
    return capfirst(name.replace("_", " "))


def format_value(value: Any) -> str:
    if value is None or value == "":
        return EMPTY_VALUE
    if value is True:
        return "✓"
    if value is False:
        return "✗"
    if hasattr(value, "all"):  # related manager (m2m / reverse fk)
        return ", ".join(str(obj) for obj in value.all()) or EMPTY_VALUE
    return str(formats.localize(value, use_l10n=True))


def related_detail_url(view: CRUDView, value: Model) -> str | None:
    """Best-effort link to the related object's detail page, by the
    ``{model_name}-detail`` naming convention, in the current namespace."""
    url_name = f"{value._meta.model_name}-detail"
    if namespace := view._namespace():
        url_name = f"{namespace}:{url_name}"
    try:
        return reverse(url_name, kwargs={"pk": value.pk})
    except NoReverseMatch:
        return None


def resolve_cell(view: CRUDView, obj: Model, name: str) -> Cell:
    """Resolve one field spec against one object into a display Cell.

    Resolution order: model field (with choices/relation handling) ->
    view method called with the object -> object attribute or method.
    """
    label = field_label(view, type(obj), name)
    url: str | None = None
    field = _model_field(type(obj), name)

    if field is not None and hasattr(field, "attname"):
        if getattr(field, "choices", None):
            value = getattr(obj, f"get_{name}_display")()
        else:
            value = getattr(obj, name)
            if field.is_relation and isinstance(value, Model):
                url = related_detail_url(view, value)
    else:
        view_attr = getattr(view, name, None)
        if callable(view_attr):
            value = view_attr(obj)
        else:
            value = getattr(obj, name, None)
            if callable(value):
                value = value()

    return Cell(label=label, value=format_value(value), url=url)


def build_headers(view: CRUDView, fields: list[str]) -> list[str]:
    assert view.model is not None
    return [field_label(view, view.model, name) for name in fields]


def build_rows(view: CRUDView, objects, fields: list[str]) -> list[Row]:
    return [
        Row(
            object=obj,
            cells=[resolve_cell(view, obj, name) for name in fields],
            detail_url=view.maybe_reverse("detail", obj),
            update_url=view.maybe_reverse("update", obj),
            delete_url=view.maybe_reverse("delete", obj),
        )
        for obj in objects
    ]
