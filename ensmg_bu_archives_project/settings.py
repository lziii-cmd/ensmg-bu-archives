"""
Paramètres Django — Système de Gestion des Archives ENSMG
Conformes à la norme ISO 15489 et à la loi sénégalaise n° 2006-19.

⚠ Configuration de DÉVELOPPEMENT uniquement.
Pour la production : désactiver DEBUG, sécuriser SECRET_KEY via variable d'environnement,
passer sur PostgreSQL et configurer un stockage S3 pour les fichiers.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Sécurité ---
# ⚠ À remplacer par : SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
SECRET_KEY = 'django-insecure-fc)a$j_l(2jp-8n)k=f^k%j3cduv4&r1d@0hnm!x_)8on4g&qp'

# ⚠ Passer à False en production
DEBUG = True

ALLOWED_HOSTS = ['*']


# --- Applications installées ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Applications ENSMG
    'users',
    'archives',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ensmg_bu_archives_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ensmg_bu_archives_project.wsgi.application'


# --- Base de données ---
# ⚠ Remplacer par PostgreSQL en production :
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.environ.get('DB_NAME', 'ensmg_archives'),
#         'USER': os.environ.get('DB_USER', 'postgres'),
#         'PASSWORD': os.environ.get('DB_PASSWORD'),
#         'HOST': os.environ.get('DB_HOST', 'localhost'),
#         'PORT': os.environ.get('DB_PORT', '5432'),
#     }
# }
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --- Modèle utilisateur personnalisé ---
AUTH_USER_MODEL = 'users.CustomUser'


# --- Validation des mots de passe ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- Internationalisation ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Dakar'
USE_I18N      = True
USE_TZ        = True


# --- Fichiers statiques ---
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# --- Fichiers uploadés (archives numériques) ---
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Taille maximale d'upload : 500 Mo (pour cartes géologiques, vidéos, etc.)
DATA_UPLOAD_MAX_MEMORY_SIZE = 524_288_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 524_288_000


# --- Auto-increment par défaut ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Authentification ---
LOGIN_URL           = '/auth/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# --- Messages Bootstrap ---
from django.contrib.messages import constants as messages_constants
MESSAGE_TAGS = {
    messages_constants.DEBUG:   'secondary',
    messages_constants.INFO:    'info',
    messages_constants.SUCCESS: 'success',
    messages_constants.WARNING: 'warning',
    messages_constants.ERROR:   'danger',
}
