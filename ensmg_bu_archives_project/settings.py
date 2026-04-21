"""
Paramètres Django — Système de Gestion des Archives ENSMG
Conformes à la norme ISO 15489 et à la loi sénégalaise n° 2006-19.

Configuration via variables d'environnement (.env / python-decouple).
Copier .env.example en .env et adapter les valeurs.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Sécurité ---
SECRET_KEY    = config('DJANGO_SECRET_KEY')
DEBUG         = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


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
_db_engine = config('DB_ENGINE', default='django.db.backends.sqlite3')
_db_name   = config('DB_NAME', default=str(BASE_DIR / 'db.sqlite3'))

if _db_engine == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': _db_engine,
            'NAME': BASE_DIR / _db_name if not _db_name.startswith('/') else _db_name,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': _db_engine,
            'NAME': _db_name,
            'USER':     config('DB_USER',     default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST':     config('DB_HOST',     default='localhost'),
            'PORT':     config('DB_PORT',     default='5432'),
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
