from django.contrib import admin
from django.urls import path, include
import debug_toolbar

urlpatterns = [
    path("__debug__/", include(debug_toolbar.urls)),
    path("", include("core.urls")),         # Inclui as views principais
    path("admin/", admin.site.urls),
]
