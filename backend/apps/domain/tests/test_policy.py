import pytest
from django.contrib.auth.models import AnonymousUser

from apps.domain.models import User
from apps.domain.policies import Action, PermissionPolicy
from apps.domain.tests.factories import (
    grant,
    join,
    make_credential,
    make_team,
    make_user,
    member_of_team_with,
)

pytestmark = pytest.mark.django_db

ALL_ACTIONS = [Action.VIEW, Action.DOWNLOAD, Action.UPLOAD]


@pytest.fixture
def credential():
    return make_credential()


class TestPerActionGrantAndDeny:
    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_allowed_when_some_team_has_the_flag(self, credential, action):
        user = member_of_team_with(credential, **{action.value: True})
        assert PermissionPolicy.can(user, action, credential) is True

    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_denied_when_flag_is_false(self, credential, action):
        user = member_of_team_with(credential)
        assert PermissionPolicy.can(user, action, credential) is False

    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_flag_grants_only_its_own_action(self, credential, action):
        user = member_of_team_with(credential, **{action.value: True})
        for other in ALL_ACTIONS:
            expected = other is action
            assert PermissionPolicy.can(user, other, credential) is expected


class TestSpecScenarios:
    def test_providers_case_upload_without_download(self, credential):
        user = member_of_team_with(credential, upload=True)
        assert PermissionPolicy.can(user, Action.UPLOAD, credential) is True
        assert PermissionPolicy.can(user, Action.DOWNLOAD, credential) is False
        assert PermissionPolicy.can(user, Action.VIEW, credential) is False

    def test_union_across_teams(self, credential):
        user = make_user("multi@example.com")
        team_a, team_b = make_team("A"), make_team("B")
        join(user, team_a)
        join(user, team_b)
        grant(team_a, credential, view=True)
        grant(team_b, credential, download=True)
        assert PermissionPolicy.can(user, Action.VIEW, credential) is True
        assert PermissionPolicy.can(user, Action.DOWNLOAD, credential) is True
        assert PermissionPolicy.can(user, Action.UPLOAD, credential) is False

    def test_user_with_no_teams_gets_nothing(self, credential):
        user = make_user("loner@example.com")
        assert PermissionPolicy.allowed_actions(user, credential) == set()
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can(user, action, credential) is False

    def test_team_without_permission_row_gets_nothing(self, credential):
        user = make_user("rowless@example.com")
        team = make_team("no-row-team")
        join(user, team)
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can(user, action, credential) is False
        assert PermissionPolicy.allowed_actions(user, credential) == set()

    def test_admin_role_grants_no_drive_actions(self, credential):
        admin_without_teams = make_user("admin1@example.com", role=User.Role.ADMIN)
        assert admin_without_teams.is_administrator is True
        assert PermissionPolicy.can(admin_without_teams, Action.DOWNLOAD, credential) is False
        assert PermissionPolicy.allowed_actions(admin_without_teams, credential) == set()

        admin_in_flagless_team = make_user("admin2@example.com", role=User.Role.ADMIN)
        team = make_team("admins")
        join(admin_in_flagless_team, team)
        grant(team, credential)
        assert PermissionPolicy.can(admin_in_flagless_team, Action.DOWNLOAD, credential) is False
        assert PermissionPolicy.allowed_actions(admin_in_flagless_team, credential) == set()

    def test_credential_isolation(self):
        cred_a = make_credential("Drive A", active=True)
        cred_b = make_credential("Drive B", active=False)
        user = member_of_team_with(cred_a, view=True, download=True, upload=True)
        assert PermissionPolicy.allowed_actions(user, cred_a) == {
            Action.VIEW,
            Action.DOWNLOAD,
            Action.UPLOAD,
        }
        assert PermissionPolicy.allowed_actions(user, cred_b) == set()
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can(user, action, cred_b) is False

    def test_allowed_actions_exact_set_mixed_case(self, credential):
        user = make_user("mixed@example.com")
        t1, t2, t3 = make_team("t1"), make_team("t2"), make_team("t3")
        for team in (t1, t2, t3):
            join(user, team)
        grant(t1, credential, view=True)
        grant(t2, credential, view=True, upload=True)
        grant(t3, credential)
        assert PermissionPolicy.allowed_actions(user, credential) == {
            Action.VIEW,
            Action.UPLOAD,
        }


class TestActiveCredentialHelpers:
    def test_can_on_active_with_no_credentials_at_all(self):
        user = make_user()
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can_on_active(user, action) is False

    def test_can_on_active_when_only_inactive_credentials_exist(self):
        cred = make_credential(active=False)
        user = member_of_team_with(cred, download=True)
        assert PermissionPolicy.can_on_active(user, Action.DOWNLOAD) is False

    def test_can_on_active_resolves_the_active_credential(self):
        make_credential("Old", active=False)
        active = make_credential("Current", active=True)
        user = member_of_team_with(active, download=True)
        assert PermissionPolicy.can_on_active(user, Action.DOWNLOAD) is True
        assert PermissionPolicy.can_on_active(user, Action.UPLOAD) is False

    def test_permissions_on_inactive_credential_do_not_leak_to_active(self):
        make_credential("Current", active=True)
        inactive = make_credential("Old", active=False)
        user = member_of_team_with(inactive, download=True)
        assert PermissionPolicy.can_on_active(user, Action.DOWNLOAD) is False

    def test_allowed_actions_on_active_empty_without_active(self):
        user = make_user()
        assert PermissionPolicy.allowed_actions_on_active(user) == set()


class TestHostileSubjects:
    def test_anonymous_user_denied(self, credential):
        anon = AnonymousUser()
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can(anon, action, credential) is False
        assert PermissionPolicy.allowed_actions(anon, credential) == set()

    def test_none_user_denied(self, credential):
        assert PermissionPolicy.can(None, Action.VIEW, credential) is False
        assert PermissionPolicy.allowed_actions(None, credential) == set()

    def test_disabled_user_denied_even_with_grants(self, credential):
        user = member_of_team_with(credential, view=True, download=True, upload=True)
        user.is_active = False
        user.save()
        for action in ALL_ACTIONS:
            assert PermissionPolicy.can(user, action, credential) is False
        assert PermissionPolicy.allowed_actions(user, credential) == set()

    def test_none_credential_denied(self):
        user = make_user()
        assert PermissionPolicy.can(user, Action.VIEW, None) is False
        assert PermissionPolicy.allowed_actions(user, None) == set()

    def test_action_accepts_enum_value_strings(self, credential):
        user = member_of_team_with(credential, download=True)
        assert PermissionPolicy.can(user, "download", credential) is True
        assert PermissionPolicy.can(user, "upload", credential) is False

    def test_unknown_action_raises(self, credential):
        user = make_user()
        with pytest.raises(ValueError):
            PermissionPolicy.can(user, "delete", credential)


class TestQueryEfficiency:
    def test_can_is_one_query(self, credential, django_assert_num_queries):
        user = member_of_team_with(credential, download=True)

        for i in range(3):
            team = make_team(f"extra-{i}")
            join(user, team)
            grant(team, credential, view=True)
        with django_assert_num_queries(1):
            assert PermissionPolicy.can(user, Action.DOWNLOAD, credential) is True

    def test_allowed_actions_is_one_query(self, credential, django_assert_num_queries):
        user = member_of_team_with(credential, view=True)
        for i in range(3):
            team = make_team(f"extra-{i}")
            join(user, team)
            grant(team, credential, download=True)
        with django_assert_num_queries(1):
            assert PermissionPolicy.allowed_actions(user, credential) == {
                Action.VIEW,
                Action.DOWNLOAD,
            }
