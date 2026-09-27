import os
os.environ.setdefault('DJANGO_SECRET_KEY', 'build-time-dummy-key-not-used-in-production-xyzzy')

from .settings import *

DATABASES = {}

