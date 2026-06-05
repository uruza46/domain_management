from .settings import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "build-only-secret-key"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "build.sqlite3",
    }
}
