from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent"
    verbose_name = "AI Agent"

    def ready(self):
        from . import receivers  # noqa: F401 - connects the signal receivers
