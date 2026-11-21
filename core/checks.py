"""Project-specific system checks (run by `manage.py check --deploy`)."""

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def secret_key_is_not_the_dev_default(app_configs, **kwargs):
    if settings.SECRET_KEY == settings.DEV_SECRET_KEY:
        return [
            Error(
                "DJANGO_SECRET_KEY is not set; the development default is in use.",
                hint="Set DJANGO_SECRET_KEY to a long random value.",
                id="patrol.E001",
            )
        ]
    return []

