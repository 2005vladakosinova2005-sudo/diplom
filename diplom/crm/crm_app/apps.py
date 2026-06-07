from django.apps import AppConfig

class CrmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_app' # Перевірте, щоб тут була назва саме вашої папки

    def ready(self):
        # Цей рядок підключає ваші сигнали
        import crm_app.signals 
