from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path("", include("core.urls")),         # Inclui as views principais
    path("site-admin/", admin.site.urls),  # was "admin/"
]

if settings.DEBUG and getattr(settings, "SHOW_DEBUG_TOOLBAR", False):
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
