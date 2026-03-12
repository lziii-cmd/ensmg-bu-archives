"""
Configuration des URLs — Système de Gestion des Archives ENSMG
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('archives.urls', namespace='archives')),
]

# Servir les fichiers médias (archives numériques) en développement
# ⚠ En production, déléguer à Nginx/Apache ou un stockage S3
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
