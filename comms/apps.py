from django.apps import AppConfig


class CommsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comms"
    verbose_name = "Command-centre messaging"

    def ready(self):
        from . import receivers  # noqa: F401 - connects the signal receivers
