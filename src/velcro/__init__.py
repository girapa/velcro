"""velcro: production-ready CRUD views for Django.

An homage to Neapolitan — same one-class, one-splat feel; adds open
actions, namespace-aware URLs, permissions, messages, search/ordering,
value rendering, and HTMX partials on Django 6.

Quickstart::

    from velcro import CRUDView

    class BookmarkView(CRUDView):
        model = Bookmark
        fields = ["url", "title", "note"]

    urlpatterns = [*BookmarkView.get_urls()]
"""

from .actions import (
    CREATE,
    DEFAULT_ACTIONS,
    DELETE,
    DETAIL,
    LIST,
    LOOKUP,
    UPDATE,
    Action,
    action,
)
from .views import CRUDView

__version__ = "0.1.0"

__all__ = [
    "Action",
    "action",
    "CRUDView",
    "DEFAULT_ACTIONS",
    "LIST",
    "CREATE",
    "DETAIL",
    "UPDATE",
    "DELETE",
    "LOOKUP",
    "__version__",
]
