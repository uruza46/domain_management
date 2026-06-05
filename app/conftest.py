import pytest


@pytest.fixture(autouse=True)
def configure_for_tests(settings):
    settings.AXES_ENABLED = False
    settings.STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        }
    }
