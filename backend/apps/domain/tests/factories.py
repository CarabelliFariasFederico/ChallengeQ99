from apps.domain.models import (
    DriveCredential,
    GroupDrivePermission,
    Membership,
    Team,
    User,
)


def make_user(email="user@example.com", role=User.Role.MEMBER, password="irrelevant", **kwargs):
    return User.objects.create_user(email=email, password=password, role=role, **kwargs)


def make_team(name="Team"):
    return Team.objects.create(name=name)


def make_credential(
    label="Main Drive",
    *,
    active=True,
    auth_method=DriveCredential.AuthMethod.OAUTH,
):
    return DriveCredential.objects.create(
        account_label=label,
        auth_method=auth_method,
        is_active=active,
    )


def join(user, team):
    return Membership.objects.create(user=user, team=team)


def grant(team, credential, *, view=False, download=False, upload=False):
    return GroupDrivePermission.objects.create(
        team=team,
        credential=credential,
        can_view=view,
        can_download=download,
        can_upload=upload,
    )


def member_of_team_with(
    credential, *, view=False, download=False, upload=False, email="member@example.com"
):
    user = make_user(email)
    team = make_team(f"team-for-{email}")
    join(user, team)
    grant(team, credential, view=view, download=download, upload=upload)
    return user
