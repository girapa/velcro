import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import include, path

from velcro.actions import action
from velcro.views import CRUDView

from .models import Bookmark

FORM = {"url": "https://new.example", "title": "New", "note": ""}


class OpenView(CRUDView):
    """No access control: used for message and next= tests."""

    model = Bookmark
    fields = ["url", "title", "note"]
    url_base = "open"
    url_name_prefix = "open"


class CustomMessageView(OpenView):
    url_base = "msg"
    url_name_prefix = "msg"
    create_success_message = "Saved {object} ({verbose_name})!"
    delete_success_message = ""  # disabled


class GuardedView(CRUDView):
    model = Bookmark
    fields = ["url", "title", "note"]
    url_base = "guarded"
    url_name_prefix = "guarded"
    login_required = True
    permissions = "model"

    @action(detail=True, methods=["post"], permission="change")
    def archive(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = Bookmark.Status.ARCHIVED
        self.object.save()
        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(self.reverse("list"))


class PublicListView(GuardedView):
    """Dict overrides: list is public, everything else stays guarded."""

    url_base = "mixed"
    url_name_prefix = "mixed"
    login_required = False
    permissions = {"list": None}


urlpatterns = [
    path("", include(OpenView.get_urls())),
    path("", include(CustomMessageView.get_urls())),
    path("", include(GuardedView.get_urls())),
    path("", include(PublicListView.get_urls())),
]


pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_access")]


@pytest.fixture
def bookmark():
    return Bookmark.objects.create(url="https://example.com", title="Example")


@pytest.fixture
def client():
    return Client()


def grant(user, *codenames):
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    return User.objects.get(pk=user.pk)  # refresh perm cache


@pytest.fixture
def user(db):
    return User.objects.create_user("u", password="p")


def flashed(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class TestMessages:
    def test_default_create_message(self, client, db):
        response = client.post("/open/new/", FORM)
        assert flashed(response) == ["Bookmark created."]

    def test_default_update_and_delete_messages(self, client, bookmark):
        response = client.post(f"/open/{bookmark.pk}/edit/", FORM | {"url": bookmark.url})
        assert flashed(response)[-1] == "Bookmark updated."
        response = client.post(f"/open/{bookmark.pk}/delete/")
        assert flashed(response)[-1] == "Bookmark deleted."

    def test_custom_message_with_placeholders(self, client, db):
        response = client.post("/msg/new/", FORM)
        assert flashed(response) == ["Saved New (bookmark)!"]

    def test_empty_string_disables_message(self, client, bookmark):
        response = client.post(f"/msg/{bookmark.pk}/delete/")
        assert flashed(response) == []


class TestNextRedirect:
    def test_safe_next_wins(self, client, db):
        response = client.post("/open/new/?next=/elsewhere/", FORM)
        assert response.url == "/elsewhere/"

    def test_next_in_post_body(self, client, db):
        response = client.post("/open/new/", FORM | {"next": "/from-post/"})
        assert response.url == "/from-post/"

    def test_unsafe_next_ignored(self, client, db):
        response = client.post("/open/new/?next=https://evil.example/", FORM)
        new = Bookmark.objects.get(title="New")
        assert response.url == f"/open/{new.pk}/"  # default policy instead


class TestLoginRequired:
    def test_anonymous_redirected_to_login(self, client, bookmark):
        response = client.get("/guarded/")
        assert response.status_code == 302
        assert response.url == "/accounts/login/?next=/guarded/"


class TestPermissions:
    def test_authenticated_without_perm_gets_403(self, client, user, bookmark):
        client.force_login(user)
        assert client.get("/guarded/").status_code == 403
        assert client.post("/guarded/new/", FORM).status_code == 403

    def test_each_shorthand_maps_to_model_permission(self, client, user, bookmark):
        client.force_login(grant(user, "view_bookmark"))
        assert client.get("/guarded/").status_code == 200
        assert client.get(f"/guarded/{bookmark.pk}/").status_code == 200
        assert client.get("/guarded/new/").status_code == 403  # needs add

        client.force_login(grant(user, "add_bookmark"))
        response = client.post("/guarded/new/", FORM)
        assert response.status_code == 302
        assert Bookmark.objects.filter(title="New").exists()

    def test_delete_requires_delete_perm(self, client, user, bookmark):
        client.force_login(grant(user, "view_bookmark"))
        assert client.post(f"/guarded/{bookmark.pk}/delete/").status_code == 403
        client.force_login(grant(user, "delete_bookmark"))
        assert client.post(f"/guarded/{bookmark.pk}/delete/").status_code == 302

    def test_custom_action_permission_expands(self, client, user, bookmark):
        client.force_login(user)
        assert client.post(f"/guarded/{bookmark.pk}/archive/").status_code == 403
        client.force_login(grant(user, "change_bookmark", "view_bookmark"))
        client.post(f"/guarded/{bookmark.pk}/archive/")
        bookmark.refresh_from_db()
        assert bookmark.status == Bookmark.Status.ARCHIVED

    def test_dict_override_makes_list_public(self, client, bookmark):
        assert client.get("/mixed/").status_code == 200  # public
        assert client.get(f"/mixed/{bookmark.pk}/").status_code == 403  # still guarded

    def test_has_permission_override_hook(self, client, user, bookmark):
        class OwnerOnly(GuardedView):
            login_required = False

            def has_permission(self, obj=None):
                return self.request.user.username == "owner"

        view = OwnerOnly.as_view(action=OwnerOnly.get_actions()[0])
        # Hook is consulted by dispatch: a plain user is denied.
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.user = user
        from django.core.exceptions import PermissionDenied

        with pytest.raises(PermissionDenied):
            view(request)
