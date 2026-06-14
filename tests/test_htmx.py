import json

import pytest
from django.test import Client
from django.urls import include, path

from velcro.views import CRUDView

from .models import Bookmark

HX = {"HTTP_HX_REQUEST": "true"}
FORM = {"url": "https://new.example", "title": "New", "note": ""}


class HtmxCRUD(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]
    template_dir = "nope"  # use bundled templates (which define partials)


class NoEventsCRUD(HtmxCRUD):
    url_base = "noevents"
    url_name_prefix = "noevents"
    htmx_events = False


class AppOverrideCRUD(HtmxCRUD):
    """tests/bookmark_list.html exists but defines NO partials: the
    candidate chain must fall back to velcro/object_list.html#table."""

    url_base = "override"
    url_name_prefix = "override"
    template_dir = "tests"


urlpatterns = [
    path("", include(HtmxCRUD.get_urls())),
    path("", include(NoEventsCRUD.get_urls())),
    path("", include(AppOverrideCRUD.get_urls())),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_htmx")]


@pytest.fixture
def bookmark():
    return Bookmark.objects.create(url="https://example.com", title="Example")


@pytest.fixture
def client():
    return Client()


class TestPartialRendering:
    def test_plain_request_gets_full_page(self, client, bookmark):
        html = client.get("/bookmarks/").content.decode()
        assert "<html>" in html and "<h1>" in html

    def test_htmx_request_gets_table_partial_only(self, client, bookmark):
        response = client.get("/bookmarks/", **HX)
        html = response.content.decode()
        assert "<table" in html and "Example" in html
        assert "<html>" not in html and "<h1>" not in html

    def test_hx_push_url_set_on_list_partial(self, client, bookmark):
        response = client.get("/bookmarks/?q=x", **HX)
        assert response.headers["HX-Push-Url"] == "/bookmarks/?q=x"

    def test_boosted_request_gets_full_page(self, client, bookmark):
        response = client.get("/bookmarks/", **HX, HTTP_HX_BOOSTED="true")
        assert "<html>" in response.content.decode()
        assert "HX-Push-Url" not in response.headers

    def test_form_partial(self, client, db):
        html = client.get("/bookmarks/new/", **HX).content.decode()
        assert '<form method="post"' in html
        assert "<html>" not in html

    def test_detail_has_no_partial_mapping_full_page(self, client, bookmark):
        html = client.get(f"/bookmarks/{bookmark.pk}/", **HX).content.decode()
        assert "<html>" in html

    def test_override_without_partial_falls_back_to_bundled(self, client, bookmark):
        # Full page uses the app override...
        assert "list|action=list" in client.get("/override/").content.decode()
        # ...partial request falls through to the bundled template's partial.
        html = client.get("/override/", **HX).content.decode()
        assert "<table" in html and "list|action=list" not in html


class TestMutationResponses:
    def test_create_returns_204_with_trigger(self, client, db):
        response = client.post("/bookmarks/new/", FORM, **HX)
        assert response.status_code == 204
        payload = json.loads(response.headers["HX-Trigger"])
        new = Bookmark.objects.get(title="New")
        assert payload == {"bookmarkChanged": {"action": "create", "pk": new.pk}}

    def test_invalid_form_rerenders_form_partial(self, client, db):
        response = client.post("/bookmarks/new/", {"url": "bad", "title": ""}, **HX)
        html = response.content.decode()
        assert response.status_code == 200
        assert '<form method="post"' in html and "<html>" not in html

    def test_delete_returns_204_with_trigger(self, client, bookmark):
        pk = bookmark.pk
        response = client.post(f"/bookmarks/{pk}/delete/", **HX)
        assert response.status_code == 204
        payload = json.loads(response.headers["HX-Trigger"])
        assert payload == {"bookmarkChanged": {"action": "delete", "pk": pk}}
        assert not Bookmark.objects.exists()

    def test_htmx_events_false_redirects_normally(self, client, db):
        response = client.post("/noevents/new/", FORM, **HX)
        assert response.status_code == 302

    def test_non_htmx_post_still_redirects(self, client, db):
        response = client.post("/bookmarks/new/", FORM)
        assert response.status_code == 302
