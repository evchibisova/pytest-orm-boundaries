pytest_plugins = ["pytester"]

try:
    import django
    from django.conf import settings
except ImportError:  # Django is optional; the integration test skips without it.
    django = None


def pytest_configure(config):
    if django is not None and not settings.configured:
        settings.configure(
            INSTALLED_APPS=["django.contrib.contenttypes"],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        )
        django.setup()
