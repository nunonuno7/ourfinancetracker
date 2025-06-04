from django.apps import AppConfig

from django.db.models.signals import post_migrate
from django.core.management import call_command

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa



def load_initial_data(sender, **kwargs):
    call_command('loaddata', 'core/fixtures/initial_data.json')

post_migrate.connect(load_initial_data)
