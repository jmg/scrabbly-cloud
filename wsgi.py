import os
import sys

sys.stdout = sys.stderr

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scrabbly_cloud.settings")
os.environ['PYTHON_EGG_CACHE'] = '/home/scrabbly/scrabblycloud/.python-eggs'

import django.core.handlers.wsgi
_application = django.core.handlers.wsgi.WSGIHandler()

def application(environ, start_response):
    os.environ['ENV'] = environ['ENV']
    return _application(environ, start_response)
