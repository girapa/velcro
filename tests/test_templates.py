import pytest
from django.test import Client
from django.urls import include, path

from velcro.renderers import EMPTY_VALUE, resolve_cell
from velcro.views import CRUDView

from .models import Bookmark, Collection


class CollectionCRUD(CRUDView):
    model = Collection
    fields = ["name"]
    template_dir = "nope"  # force fallback to bundled velcro templates


class BookmarkCRUD(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note", "favourite", "status", "collection"]
    list_fields = ["title", "favourite", "status", "collection", "domain"]
    template_dir = "nope"  # force fallback to bundled velcro templates
    paginate_by = 2

    def domain(self, obj):
        return obj.url.split("/")[2]

    domain.short_description = "Site domain"


urlpatterns = [
    path("", include(BookmarkCRUD.get_urls())),
    path("", include(CollectionCRUD.get_urls())),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_templates")]


@pytest.fixture
def collection():
    return Collection.objects.create(name="Reading")


@pytest.fixture
def bookmark(collection):
    return Bookmark.objects.create(
        url="https://example.com/page",
        title="Example",
        favourite=True,
        collection=collection,
    )


@pytest.fixture
def client():
    return Client()


class TestListTemplate:
    def test_headers_from_labels(self, client, bookmark):
        html = client.get("/bookmark/").content.decode()
        for header in ("Title", "Favourite", "Status", "Collection", "Site domain"):
            assert f'<th scope="col">{header}</th>' in html

    def test_choices_render_display_label(self, client, bookmark):
        html = client.get("/bookmark/").content.decode()
        assert "<td>Active</td>" in html
        assert "<td>active</td>" not in html  # Neapolitan issue #82

    def test_boolean_renders_check(self, client, bookmark):
        assert "<td>✓</td>" in client.get("/bookmark/").content.decode()

    def test_view_method_column(self, client, bookmark):
        assert "<td>example.com</td>" in client.get("/bookmark/").content.decode()

    def test_fk_cell_links_to_related_detail(self, client, bookmark, collection):
        html = client.get("/bookmark/").content.decode()
        assert f'<a href="/collection/{collection.pk}/">Reading</a>' in html

    def test_row_action_links(self, client, bookmark):
        html = client.get("/bookmark/").content.decode()
        assert f'href="/bookmark/{bookmark.pk}/edit/"' in html
        assert f'href="/bookmark/{bookmark.pk}/delete/"' in html

    def test_empty_state(self, client, db):
        assert "No bookmarks yet." in client.get("/bookmark/").content.decode()

    def test_pagination_uses_querystring_tag(self, client, collection, db):
        for i in range(3):
            Bookmark.objects.create(url=f"https://e{i}.com", title=f"B{i}")
        html = client.get("/bookmark/?favourite=x").content.decode()
        # {% querystring %} preserves existing params while changing page.
        assert "?favourite=x&amp;page=2" in html or "?page=2&amp;favourite=x" in html

    def test_create_link_present(self, client, db):
        assert 'href="/bookmark/new/"' in client.get("/bookmark/").content.decode()


class TestDetailTemplate:
    def test_fields_rendered_as_definition_list(self, client, bookmark):
        html = client.get(f"/bookmark/{bookmark.pk}/").content.decode()
        assert "<dt>Status</dt>" in html
        assert "<dd>Active</dd>" in html
        assert "<dt>Note</dt>" in html
        assert f"<dd>{EMPTY_VALUE}</dd>" in html  # blank note

    def test_edit_and_delete_links(self, client, bookmark):
        html = client.get(f"/bookmark/{bookmark.pk}/").content.decode()
        assert f'href="/bookmark/{bookmark.pk}/edit/"' in html
        assert f'href="/bookmark/{bookmark.pk}/delete/"' in html


class TestFormAndDeleteTemplates:
    def test_form_renders_with_csrf(self, client, db):
        html = client.get("/bookmark/new/").content.decode()
        assert '<form method="post"' in html
        assert "csrfmiddlewaretoken" in html
        assert "New bookmark" in html

    def test_update_form_says_edit(self, client, bookmark):
        html = client.get(f"/bookmark/{bookmark.pk}/edit/").content.decode()
        assert "Edit bookmark" in html

    def test_confirm_delete_page(self, client, bookmark):
        html = client.get(f"/bookmark/{bookmark.pk}/delete/").content.decode()
        assert "Confirm deletion" in html
        assert "Example" in html

    def test_next_passed_through_as_hidden_input(self, client, bookmark):
        html = client.get(f"/bookmark/{bookmark.pk}/edit/?next=/back/").content.decode()
        assert '<input type="hidden" name="next" value="/back/">' in html


class TestResolveCellUnit:
    def test_none_fk_renders_empty(self, bookmark):
        bookmark.collection = None
        view = BookmarkCRUD()
        view.action = BookmarkCRUD.get_actions()[0]
        cell = resolve_cell(view, bookmark, "collection")
        assert cell.value == EMPTY_VALUE
        assert cell.url is None

    def test_model_method_resolution(self, bookmark):
        view = BookmarkCRUD()
        view.action = BookmarkCRUD.get_actions()[0]
        # __str__ exists on the model; arbitrary model attrs resolve too.
        cell = resolve_cell(view, bookmark, "pk")
        assert cell.value == str(bookmark.pk)
