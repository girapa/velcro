import pytest
from django.http import HttpResponseRedirect
from django.test import Client
from django.urls import path

from velcro import actions as A
from velcro.actions import action
from velcro.views import CRUDView

from .models import Bookmark


class BookmarkView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]
    list_fields = ["title"]  # per-action override
    success_url = "/done/"  # explicit until step 4 wires reversing

    @action(detail=True, methods=["post"], name="archive")
    def archive(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = Bookmark.Status.ARCHIVED
        self.object.save()
        return HttpResponseRedirect("/archived/")

    @action(detail=False, name="archived")
    def archived(self, request, *args, **kwargs):
        self.object_list = self.get_queryset().filter(status=Bookmark.Status.ARCHIVED)
        return self.render_to_response(self.get_context_data())

    def get_list_context_data(self, context):
        context["banner"] = "from-hook"
        return context


class PaginatedView(BookmarkView):
    paginate_by = 2


class DashboardView(BookmarkView):
    template_dir = "dashboard"


urlpatterns = [
    path("bm/", BookmarkView.as_view(action=A.LIST), name="bm-list"),
    path("bm/new/", BookmarkView.as_view(action=A.CREATE), name="bm-create"),
    path("bm/<int:pk>/", BookmarkView.as_view(action=A.DETAIL), name="bm-detail"),
    path("bm/<int:pk>/edit/", BookmarkView.as_view(action=A.UPDATE), name="bm-update"),
    path("bm/<int:pk>/delete/", BookmarkView.as_view(action=A.DELETE), name="bm-delete"),
    path(
        "bm/<int:pk>/archive/",
        BookmarkView.as_view(action=next(a for a in BookmarkView.get_actions() if a.name == "archive")),
        name="bm-archive",
    ),
    path(
        "bm/archived/",
        BookmarkView.as_view(action=next(a for a in BookmarkView.get_actions() if a.name == "archived")),
        name="bm-archived",
    ),
    path("paged/", PaginatedView.as_view(action=A.LIST), name="paged-list"),
    path("dash/", DashboardView.as_view(action=A.LIST), name="dash-list"),
]


pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("tests.test_views"),
]


@pytest.fixture
def bookmark():
    return Bookmark.objects.create(url="https://example.com", title="Example")


@pytest.fixture
def client():
    return Client()


class TestStandardActions:
    def test_list(self, client, bookmark):
        response = client.get("/bm/")
        assert response.status_code == 200
        assert b"action=list" in response.content
        assert b"count=1" in response.content

    def test_detail(self, client, bookmark):
        response = client.get(f"/bm/{bookmark.pk}/")
        assert b"obj=Example" in response.content

    def test_detail_404(self, client, db):
        assert client.get("/bm/999/").status_code == 404

    def test_create_get_shows_form(self, client, db):
        response = client.get("/bm/new/")
        assert b"form=yes" in response.content

    def test_create_post_valid(self, client, db):
        response = client.post("/bm/new/", {"url": "https://new.example", "title": "New", "note": ""})
        assert response.status_code == 302
        assert response.url == "/done/"
        assert Bookmark.objects.filter(title="New").exists()

    def test_create_post_invalid_rerenders(self, client, db):
        response = client.post("/bm/new/", {"url": "not-a-url", "title": ""})
        assert response.status_code == 200
        assert b"form=yes" in response.content
        assert Bookmark.objects.count() == 0

    def test_update(self, client, bookmark):
        response = client.post(
            f"/bm/{bookmark.pk}/edit/",
            {"url": bookmark.url, "title": "Renamed", "note": ""},
        )
        assert response.status_code == 302
        bookmark.refresh_from_db()
        assert bookmark.title == "Renamed"

    def test_delete_confirm_then_post(self, client, bookmark):
        assert client.get(f"/bm/{bookmark.pk}/delete/").status_code == 200
        response = client.post(f"/bm/{bookmark.pk}/delete/")
        assert response.status_code == 302
        assert not Bookmark.objects.exists()

    def test_wrong_method_rejected(self, client, bookmark):
        # LIST only binds GET; POST should 405.
        assert client.post("/bm/").status_code == 405


class TestCustomActions:
    def test_post_only_custom_action(self, client, bookmark):
        assert client.get(f"/bm/{bookmark.pk}/archive/").status_code == 405
        response = client.post(f"/bm/{bookmark.pk}/archive/")
        assert response.status_code == 302
        bookmark.refresh_from_db()
        assert bookmark.status == Bookmark.Status.ARCHIVED

    def test_get_custom_action_renders_template(self, client, bookmark):
        bookmark.status = Bookmark.Status.ARCHIVED
        bookmark.save()
        response = client.get("/bm/archived/")
        assert b"action=archived" in response.content
        assert b"count=1" in response.content

    def test_get_actions_registry(self):
        names = {a.name for a in BookmarkView.get_actions()}
        assert names == {"list", "create", "detail", "update", "delete", "archive", "archived"}


class TestConfigResolution:
    def test_per_action_fields_fall_back(self, bookmark):
        view = BookmarkView()
        view.action = A.LIST
        assert view.get_fields() == ["title"]  # list_fields wins
        view.action = A.DETAIL
        assert view.get_fields() == ["url", "title", "note"]  # falls back

    def test_per_action_context_hook(self, client, bookmark):
        response = client.get("/bm/")
        assert b"banner=from-hook" in response.content
        # Hook is list-only: detail response has no banner.
        response = client.get(f"/bm/{bookmark.pk}/")
        assert b"banner" not in response.content

    def test_template_dir_overrides_app_label(self, client, bookmark):
        response = client.get("/dash/")
        assert b"dash-list" in response.content

    def test_pagination(self, client, db):
        for i in range(5):
            Bookmark.objects.create(url=f"https://e{i}.com", title=f"B{i}")
        response = client.get("/paged/")
        assert b"count=2" in response.content
        response = client.get("/paged/?page=3")
        assert b"count=1" in response.content
        assert client.get("/paged/?page=99").status_code == 404
        assert client.get("/paged/?page=last").status_code == 200

    def test_as_view_rejects_handler_kwargs(self):
        with pytest.raises(TypeError, match="handler"):
            BookmarkView.as_view(action=A.LIST, list="nope")

    def test_as_view_rejects_unknown_kwargs(self):
        with pytest.raises(TypeError, match="invalid keyword"):
            BookmarkView.as_view(action=A.LIST, bogus=True)
