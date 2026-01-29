from django.apps import AppConfig


class GrantsConfig(AppConfig):
    name = 'grants'
    
    def ready(self):
        import grants.signals
