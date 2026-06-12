"""
The Action system.

Where Neapolitan uses a closed ``Role`` enum (LIST/CREATE/DETAIL/UPDATE/DELETE),
velcro models each operation as an ``Action`` — a frozen dataclass describing:

* which HTTP methods map to which view methods (``handlers``),
* the URL pattern fragment it contributes (``url_pattern``),
* whether it operates on a single object (``detail``),
* its template suffix and default permission.

The five CRUD actions are provided as module-level constants, and views can
add, remove, or replace actions freely. The ``@action`` decorator registers a
view method as a custom action inline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

# Placeholder substituted at URL-generation time with the view's
# "<path_converter:lookup_url_kwarg>" fragment, e.g. "<int:pk>".
LOOKUP = "{lookup}"


@dataclass(frozen=True, slots=True)
class Action:
    """A single named operation a CRUDView can perform."""

    name: str
    # Mapping of HTTP method -> view method name, e.g. {"get": "list"}.
    handlers: dict[str, str] = field(default_factory=dict)
    # URL fragment appended to the view's url_base. May contain LOOKUP.
    # "" means the collection root; trailing slash is added by the view.
    url_pattern: str = ""
    # Does this action operate on a single object (needs lookup + get_object)?
    detail: bool = False
    # Suffix for template discovery: "{model}{suffix}.html". None = no template
    # of its own (e.g. pure-POST actions that redirect).
    template_suffix: str | None = None
    # Default permission shorthand checked when the view enables permissions.
    # One of: "view", "add", "change", "delete", a full "app.codename" string,
    # or None for "no permission required".
    permission: str | None = None

    def __post_init__(self) -> None:
        if not self.name.isidentifier():
            raise ValueError(
                f"Action name {self.name!r} must be a valid Python identifier "
                "(it is used for view-method and URL-name lookups)."
            )
        if self.detail and LOOKUP not in self.url_pattern and self.url_pattern:
            # A detail action with a static pattern is almost always a mistake,
            # but "" is allowed for exotic cases; only warn-by-error when a
            # pattern was given without the lookup.
            raise ValueError(
                f"Detail action {self.name!r} has url_pattern {self.url_pattern!r} without a {LOOKUP!r} placeholder."
            )

    def using(self, **changes: Any) -> Action:
        """Return a copy of this action with the given fields replaced.

        Lets users tweak built-ins without redefining them::

            LIST.using(permission=None)
            UPDATE.using(url_pattern=f"{LOOKUP}/change/")
        """
        return replace(self, **changes)


# ---------------------------------------------------------------------------
# The five standard CRUD actions. These mirror Neapolitan's Role semantics
# (same handler names, same URL shapes) so migration is mechanical.
# ---------------------------------------------------------------------------

LIST = Action(
    name="list",
    handlers={"get": "list"},
    url_pattern="",
    detail=False,
    template_suffix="_list",
    permission="view",
)

CREATE = Action(
    name="create",
    handlers={"get": "show_form", "post": "process_form"},
    url_pattern="new",
    detail=False,
    template_suffix="_form",
    permission="add",
)

DETAIL = Action(
    name="detail",
    handlers={"get": "detail"},
    url_pattern=LOOKUP,
    detail=True,
    template_suffix="_detail",
    permission="view",
)

UPDATE = Action(
    name="update",
    handlers={"get": "show_form", "post": "process_form"},
    url_pattern=f"{LOOKUP}/edit",
    detail=True,
    template_suffix="_form",
    permission="change",
)

DELETE = Action(
    name="delete",
    handlers={"get": "confirm_delete", "post": "process_deletion"},
    url_pattern=f"{LOOKUP}/delete",
    detail=True,
    template_suffix="_confirm_delete",
    permission="delete",
)

DEFAULT_ACTIONS: tuple[Action, ...] = (LIST, CREATE, DETAIL, UPDATE, DELETE)


# ---------------------------------------------------------------------------
# Inline custom actions: the @action decorator.
# ---------------------------------------------------------------------------

ACTION_ATTR = "_velcro_action"


def action(
    *,
    detail: bool,
    methods: list[str] | None = None,
    url_pattern: str | None = None,
    name: str | None = None,
    template_suffix: str | None = None,
    permission: str | None = None,
) -> Callable[[Callable], Callable]:
    """Mark a CRUDView method as a custom action.

    ::

        class ProjectView(CRUDView):
            model = Project

            @action(detail=True, methods=["post"], permission="change")
            def archive(self, request, *args, **kwargs):
                self.object = self.get_object()
                self.object.archive()
                return HttpResponseRedirect(self.reverse("list"))

    Generates the URL ``{url_base}/<lookup>/archive/`` named
    ``{url_name_prefix}-archive``. GET-only actions get a template suffix of
    ``_{name}`` by default so they can render a page.
    """
    http_methods = [m.lower() for m in (methods or ["get"])]

    def decorator(func: Callable) -> Callable:
        action_name = name or func.__name__
        if url_pattern is not None:
            pattern = url_pattern
        else:
            pattern = f"{LOOKUP}/{action_name}" if detail else action_name
        suffix = template_suffix
        if suffix is None and "get" in http_methods:
            suffix = f"_{action_name}"
        setattr(
            func,
            ACTION_ATTR,
            Action(
                name=action_name,
                handlers={m: func.__name__ for m in http_methods},
                url_pattern=pattern,
                detail=detail,
                template_suffix=suffix,
                permission=permission,
            ),
        )
        return func

    return decorator


def collect_decorated_actions(cls: type) -> list[Action]:
    """Find all @action-decorated methods on a class (MRO-aware)."""
    found: dict[str, Action] = {}
    # Walk the MRO in reverse so subclasses override base-class actions.
    for klass in reversed(cls.__mro__):
        for attr_value in vars(klass).values():
            act = getattr(attr_value, ACTION_ATTR, None)
            if act is not None:
                found[act.name] = act
    return list(found.values())
