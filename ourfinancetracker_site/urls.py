"""
URL configuration for ourfinancetracker_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
import debug_toolbar

urlpatterns = [
    # Debug Toolbar (namespace 'djdt') - DEVE VIR PRIMEIRO
    path("__debug__/", include(debug_toolbar.urls)),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Aplicação principal - inclui todas as rotas do core
    path('', include('core.urls')),
]
