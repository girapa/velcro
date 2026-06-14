import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import include, path

import velcro.views
from velcro.views import CRUDView

from .models import Bookmark, Collection


class SearchableCRUD(CRUDView):
    model = Bookmark
    fields = ["title", "url", "status"]
    template_dir = "nope"
    search_fields = ["title", "^url", "collection__name"]
    ordering_fields = ["title", "status"]


class FilteredCRUD(CRUDView):
    model = Bookmark
    fields = ["title", "favourite"]
    template_dir = "nope"
    url_base = "filtered"
    url_name_prefix = "filtered"
    filterset_fields = ["favourite", "status"]
    search_fields = ["title"]


urlpatterns = [
    path("", include(SearchableCRUD.get_urls())),
    path("", include(FilteredCRUD.get_urls())),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_filtering")]


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def data(db):
    reading = Collection.objects.create(name="Reading")
    Bookmark.objects.create(url="https://alpha.example", title="Django news", favourite=True)
    Bookmark.objects.create(url="https://beta.example", title="Python tips", collection=reading)
    Bookmark.objects.create(
        url="https://gamma.example",
        title="Cooking",
        favourite=True,
        status=Bookmark.Status.ARCHIVED,
    )


def titles(response):
    return [row.object.title for row in response.context["object_table"]["rows"]]


class TestSearch:
    def test_icontains_search(self, client, data):
        response = client.get("/bookmarks/?q=django")
        assert titles(response) == ["Django news"]

    def test_startswith_prefix(self, client, data):
        response = client.get("/bookmarks/?q=beta")
        # "^url" istartswith: "beta" doesn't start the URL ("https://...").
        assert titles(response) == []
        response = client.get("/bookmarks/?q=https://beta")
        assert titles(response) == ["Python tips"]

    def test_relation_spanning_search(self, client, data):
        response = client.get("/bookmarks/?q=reading")
        assert titles(response) == ["Python tips"]

    def test_blank_query_returns_all(self, client, data):
        response = client.get("/bookmarks/?q=")
        assert len(titles(response)) == 3

    def test_search_box_rendered_with_value(self, client, data):
        html = client.get("/bookmarks/?q=django").content.decode()
        assert 'name="q" value="django"' in html


class TestOrdering:
    def test_descending(self, client, data):
        response = client.get("/bookmarks/?ordering=-title")
        assert titles(response) == ["Python tips", "Django news", "Cooking"]

    def test_multiple_fields(self, client, data):
        response = client.get("/bookmarks/?ordering=status,title")
        # "active" < "archived"; title ordering applies within each status.
        assert titles(response) == ["Django news", "Python tips", "Cooking"]

    def test_unknown_field_ignored(self, client, data):
        response = client.get("/bookmarks/?ordering=evil__field")
        assert len(titles(response)) == 3  # model default ordering, no crash

    def test_sortable_header_toggles_and_preserves_query(self, client, data):
        html = client.get("/bookmarks/?q=o").content.decode()
        assert "?q=o&amp;ordering=title" in html or "?ordering=title&amp;q=o" in html
        html = client.get("/bookmarks/?ordering=title").content.decode()
        assert 'href="?ordering=-title"' in html and "▲" in html
        html = client.get("/bookmarks/?ordering=-title").content.decode()
        assert 'href="?ordering=title"' in html and "▼" in html

    def test_unsortable_column_is_plain_text(self, client, data):
        html = client.get("/bookmarks/").content.decode()
        assert '<th scope="col">Url</th>' in html  # not in ordering_fields


class TestFilterset:
    def test_filterset_fields_filter(self, client, data):
        response = client.get("/filtered/?favourite=true")
        assert sorted(titles(response)) == ["Cooking", "Django news"]

    def test_filterset_form_rendered(self, client, data):
        html = client.get("/filtered/").content.decode()
        assert 'class="velcro-filters"' in html
        assert 'name="favourite"' in html

    def test_search_composes_with_filterset(self, client, data):
        response = client.get("/filtered/?favourite=true&q=cook")
        assert titles(response) == ["Cooking"]

    def test_no_config_means_no_filterset(self, client, data):
        response = client.get("/bookmarks/")
        assert response.context["filterset"] is None

    def test_missing_dependency_raises_clear_error(self, client, data, monkeypatch):
        def boom():
            raise ImproperlyConfigured("Using 'filterset_fields' or 'filterset_class' requires django-filter.")

        monkeypatch.setattr(velcro.views, "_filterset_factory", boom)
        with pytest.raises(ImproperlyConfigured, match="django-filter"):
            client.get("/filtered/")
