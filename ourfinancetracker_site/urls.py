"""
URL configuration for ourfinancetracker_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
import debug_toolbar

urlpatterns = [
    # Rota para a interface de administração do Django
    path('admin/', admin.site.urls),
    
    # Rota principal que inclui todas as URLs definidas em core/urls.py
    path('', include('core.urls')), 

    # Integração do Django Debug Toolbar (namespace 'djdt')
    path('__debug__/', include(debug_toolbar.urls)), 
]
