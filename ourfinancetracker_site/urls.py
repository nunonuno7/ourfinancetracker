from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", include("core.urls")),         # Inclui as views principais
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
]

if settings.DEBUG and getattr(settings, "SHOW_DEBUG_TOOLBAR", False):
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns

# Servir arquivos estáticos em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if settings.STATICFILES_DIRS: # Ensure STATICFILES_DIRS is not empty
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])