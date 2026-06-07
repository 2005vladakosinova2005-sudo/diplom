from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
# Імпортуємо ваші функції з додатка
from crm_app.views import dashboard, export_inventory_report 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),
    
    # Шляхи для входу та виходу
    path('login/', auth_views.LoginView.as_view(template_name='crm_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Шлях для експорту (використовуємо імпортовану функцію)
    path('export/stock/', export_inventory_report, name='export_inventory_report'),
]
