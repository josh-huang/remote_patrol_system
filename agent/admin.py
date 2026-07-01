from django.contrib import admin

from .models import AgentAction, AgentConversation, AgentMessage


class AgentMessageInline(admin.TabularInline):
    model = AgentMessage
    extra = 0
    readonly_fields = ["role", "content", "steps", "created_at"]


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "user", "created_at"]
    inlines = [AgentMessageInline]


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ["id", "tool_name", "origin", "status", "summary", "created_at"]
    list_filter = ["status", "origin", "tool_name"]
    readonly_fields = ["arguments", "result"]
