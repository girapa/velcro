import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import include, path

from velcro.actions import action
from velcro.views import CRUDView

from .models import Bookmark


class BookmarkCRUD(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]

    @action(detail=False, name="archived")
    def archived(self, request, *args, **kwargs):
        self.object_list = self.get_queryset().filter(status=Bookmark.Status.ARCHIVED)
        return self.render_to_response(self.get_context_data())


class RenamedCRUD(BookmarkCRUD):
    url_base = "links"
    url_name_prefix = "favourites"


class SlugLikeCRUD(BookmarkCRUD):
    """str converter on pk — would shadow static routes if unordered."""

    path_converter = "str"
    url_base = "s"
    url_name_prefix = "s"


urlpatterns = [
    path("", include((BookmarkCRUD.get_urls(), "bookmarks"))),
    path("staff/", include((BookmarkCRUD.get_urls(), "bookmarks"), namespace="staff")),
    path("admin2/", include((BookmarkCRUD.get_urls(), "bookmarks"), namespace="admin2")),
    path("renamed/", include(RenamedCRUD.get_urls())),
    path("slugged/", include(SlugLikeCRUD.get_urls())),
]


pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_urls")]


@pytest.fixture
def bookmark():
    return Bookmark.objects.create(url="https://example.com", title="Example")


@pytest.fixture
def client():
    return Client()


class TestUrlGeneration:
    def test_default_patterns_and_names(self):
        urls = BookmarkCRUD.get_urls()
        routes = {p.name: str(p.pattern) for p in urls}
        assert routes == {
            "bookmark-list": "bookmark/",
            "bookmark-create": "bookmark/new/",
            "bookmark-archived": "bookmark/archived/",
            "bookmark-detail": "bookmark/<int:pk>/",
            "bookmark-update": "bookmark/<int:pk>/edit/",
            "bookmark-delete": "bookmark/<int:pk>/delete/",
        }

    def test_subset_by_name(self):
        names = [p.name for p in BookmarkCRUD.get_urls(["list", "detail"])]
        assert names == ["bookmark-list", "bookmark-detail"]

    def test_unknown_action_name_raises(self):
        with pytest.raises(ImproperlyConfigured, match="no action named 'bogus'"):
            BookmarkCRUD.get_urls(["bogus"])

    def test_url_base_and_name_prefix_decoupled(self):
        routes = {p.name: str(p.pattern) for p in RenamedCRUD.get_urls()}
        assert routes["favourites-list"] == "links/"
        assert routes["favourites-detail"] == "links/<int:pk>/"

    def test_static_routes_precede_lookup_routes(self):
        patterns = [str(p.pattern) for p in SlugLikeCRUD.get_urls()]
        lookup_index = patterns.index("s/<str:pk>/")
        assert patterns.index("s/new/") < lookup_index
        assert patterns.index("s/archived/") < lookup_index

    def test_static_route_not_shadowed_at_request_time(self, client, db):
        # With str converter, /slugged/s/new/ must hit CREATE, not DETAIL.
        response = client.get("/slugged/s/new/")
        assert response.status_code == 200
        assert b"form=yes" in response.content


class TestNamespaceAwareReversing:
    def test_unnamespaced_default_success_urls(self, client, bookmark, db):
        response = client.post(
            "/bookmark/new/",
            {"url": "https://a.example", "title": "A", "note": ""},
        )
        new = Bookmark.objects.get(title="A")
        assert response.url == f"/bookmark/{new.pk}/"  # create -> detail
        response = client.post(f"/bookmark/{new.pk}/delete/")
        assert response.url == "/bookmark/"  # delete -> list

    def test_namespaced_mount_redirects_within_namespace(self, client, db):
        response = client.post(
            "/staff/bookmark/new/",
            {"url": "https://b.example", "title": "B", "note": ""},
        )
        new = Bookmark.objects.get(title="B")
        assert response.url == f"/staff/bookmark/{new.pk}/"

    def test_same_view_mounted_twice_reverses_per_request(self, client, bookmark):
        # The exact failure mode of Neapolitan issue #16, doubled.
        staff = client.get(f"/staff/bookmark/{bookmark.pk}/")
        admin2 = client.get(f"/admin2/bookmark/{bookmark.pk}/")
        assert staff.context["update_view_url"] == f"/staff/bookmark/{bookmark.pk}/edit/"
        assert admin2.context["update_view_url"] == f"/admin2/bookmark/{bookmark.pk}/edit/"

    def test_context_url_helpers(self, client, bookmark):
        response = client.get(f"/bookmark/{bookmark.pk}/")
        ctx = response.context
        assert ctx["list_view_url"] == "/bookmark/"
        assert ctx["create_view_url"] == "/bookmark/new/"
        assert ctx["delete_view_url"] == f"/bookmark/{bookmark.pk}/delete/"

    def test_maybe_reverse_returns_none_for_unrouted(self, client, bookmark):
        # 'detail' exists as an action but reverse for a bogus name is None.
        response = client.get("/bookmark/")
        view = response.context["view"]
        assert view.maybe_reverse("nonexistent") is None

    def test_explicit_url_namespace_attribute_wins(self, client, bookmark):
        view_response = client.get(f"/admin2/bookmark/{bookmark.pk}/")
        view = view_response.context["view"]
        view.url_namespace = "staff"
        assert view.reverse("list") == "/staff/bookmark/"
