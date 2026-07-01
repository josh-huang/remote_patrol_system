from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import SecurityGuard, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "is_staff"]
    list_filter = ["role", "is_staff", "is_superuser"]
    fieldsets = UserAdmin.fieldsets + (
        ("Patrol", {"fields": ("role", "phone")}),
    )


@admin.register(SecurityGuard)
class SecurityGuardAdmin(admin.ModelAdmin):
    list_display = ["badge_number", "user", "on_duty", "is_available", "is_driver"]
    list_filter = ["on_duty", "is_available", "is_driver"]
    search_fields = ["badge_number"]
