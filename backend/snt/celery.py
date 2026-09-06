import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "snt.settings.dev")

app = Celery("snt")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
