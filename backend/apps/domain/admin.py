from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.domain.models import (
    AuditLog,
    DriveCredential,
    GroupDrivePermission,
    Membership,
    Team,
    User,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_staff", "is_active", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Role", {"fields": ("role",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),
    )


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "member_count")
    search_fields = ("name",)
    inlines = (MembershipInline,)

    @admin.display(description="members")
    def member_count(self, obj):
        return obj.members.count()


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "created_at")
    list_filter = ("team",)
    autocomplete_fields = ("user", "team")


@admin.register(DriveCredential)
class DriveCredentialAdmin(admin.ModelAdmin):
    exclude = ("secret_ciphertext",)
    list_display = ("account_label", "auth_method", "is_active", "key_version", "rotated_at")
    list_filter = ("auth_method", "is_active")
    search_fields = ("account_label",)

    readonly_fields = ("key_version", "rotated_at", "rotated_by", "created_at", "updated_at")


@admin.register(GroupDrivePermission)
class GroupDrivePermissionAdmin(admin.ModelAdmin):
    list_display = ("team", "credential", "can_view", "can_download", "can_upload")
    list_filter = ("credential", "can_view", "can_download", "can_upload")
    autocomplete_fields = ("team", "credential")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_type", "target_id", "ip")
    list_filter = ("action",)
    search_fields = ("target_id", "actor__email")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
