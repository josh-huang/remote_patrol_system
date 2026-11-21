from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "sender", "from_command_centre", "body", "created_at", "read_at")
    list_filter = ("from_command_centre", "vehicle")
    search_fields = ("body",)
