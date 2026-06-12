import pytest

from velcro.actions import (
    CREATE,
    DEFAULT_ACTIONS,
    DELETE,
    DETAIL,
    LIST,
    LOOKUP,
    UPDATE,
    Action,
    action,
    collect_decorated_actions,
)


class TestActionDataclass:
    def test_defaults_mirror_neapolitan_roles(self):
        assert LIST.handlers == {"get": "list"}
        assert CREATE.handlers == {"get": "show_form", "post": "process_form"}
        assert DELETE.handlers == {"get": "confirm_delete", "post": "process_deletion"}
        assert DETAIL.detail and UPDATE.detail and DELETE.detail
        assert not LIST.detail and not CREATE.detail
        assert UPDATE.url_pattern == f"{LOOKUP}/edit"
        assert len(DEFAULT_ACTIONS) == 5

    def test_using_returns_modified_copy(self):
        relaxed = LIST.using(permission=None)
        assert relaxed.permission is None
        assert LIST.permission == "view"  # original untouched
        assert relaxed.handlers == LIST.handlers

    def test_invalid_name_rejected(self):
        with pytest.raises(ValueError, match="identifier"):
            Action(name="not-valid")

    def test_detail_action_without_lookup_rejected(self):
        with pytest.raises(ValueError, match="placeholder"):
            Action(name="broken", detail=True, url_pattern="static")

    def test_actions_are_immutable(self):
        with pytest.raises(AttributeError):
            LIST.name = "hacked"


class TestActionDecorator:
    def test_detail_post_action(self):
        class FakeView:
            @action(detail=True, methods=["post"], permission="change")
            def archive(self, request):
                pass

        acts = collect_decorated_actions(FakeView)
        assert len(acts) == 1
        act = acts[0]
        assert act.name == "archive"
        assert act.handlers == {"post": "archive"}
        assert act.url_pattern == f"{LOOKUP}/archive"
        assert act.permission == "change"
        assert act.template_suffix is None  # POST-only: no template

    def test_get_action_gets_template_suffix(self):
        class FakeView:
            @action(detail=False)
            def stats(self, request):
                pass

        (act,) = collect_decorated_actions(FakeView)
        assert act.handlers == {"get": "stats"}
        assert act.url_pattern == "stats"
        assert act.template_suffix == "_stats"

    def test_subclass_overrides_base_action(self):
        class Base:
            @action(detail=True, methods=["post"])
            def archive(self, request):
                pass

        class Child(Base):
            @action(detail=True, methods=["post", "get"])
            def archive(self, request):
                pass

        (act,) = collect_decorated_actions(Child)
        assert set(act.handlers) == {"post", "get"}

    def test_custom_name_and_pattern(self):
        class FakeView:
            @action(detail=True, methods=["post"], name="dup", url_pattern=f"{LOOKUP}/duplicate")
            def duplicate_object(self, request):
                pass

        (act,) = collect_decorated_actions(FakeView)
        assert act.name == "dup"
        assert act.handlers == {"post": "duplicate_object"}
        assert act.url_pattern == f"{LOOKUP}/duplicate"
