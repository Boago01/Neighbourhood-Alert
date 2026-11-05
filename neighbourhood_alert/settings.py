"""
Django settings for neighbourhood_alert project.
"""

from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment values without overriding values provided by the host.
local_env_file = BASE_DIR / '.env'
if local_env_file.is_file():
    for line in local_env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        if separator and name.strip() and name.strip() not in os.environ:
            os.environ[name.strip()] = value.strip().strip('"').strip("'")


def _environment_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


DEBUG = _environment_bool('DEBUG', False)
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()

SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = get_random_secret_key()
    else:
        raise ImproperlyConfigured(
            'Set SECRET_KEY to a unique secret in the deployment environment.'
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', '').split(',')
    if host.strip()
]
if not ALLOWED_HOSTS:
    if DEBUG:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
    else:
        raise ImproperlyConfigured(
            'Set ALLOWED_HOSTS to the hostnames served by this deployment.'
        )

SECURE_SSL_REDIRECT = _environment_bool('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = _environment_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = _environment_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_HSTS_SECONDS = int(
    os.environ.get('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0')
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _environment_bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS',
    False,
)
SECURE_HSTS_PRELOAD = _environment_bool('SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Custom apps
    'accounts',
    'incidents',
    'volunteers',
    'donations',
    'alerts',
    'analytics',
    'problem_reports',
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

ROOT_URLCONF = 'neighbourhood_alert.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'neighbourhood_alert.context_processors.google_maps_api_key',
            ],
        },
    },
]

WSGI_APPLICATION = 'neighbourhood_alert.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
PRIVATE_PROBLEM_REPORT_ROOT = BASE_DIR / 'private_problem_reports'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# BulkSMS is disabled until API credentials are configured.
BULKSMS_ENABLED = os.environ.get('BULKSMS_ENABLED', 'false').lower() in ('1', 'true', 'yes')
BULKSMS_DRY_RUN = os.environ.get('BULKSMS_DRY_RUN', 'true').lower() in ('1', 'true', 'yes')
BULKSMS_TEST_MODE = os.environ.get('BULKSMS_TEST_MODE', 'false').lower() in ('1', 'true', 'yes')
BULKSMS_TOKEN_ID = os.environ.get('BULKSMS_TOKEN_ID', '')
BULKSMS_TOKEN_SECRET = os.environ.get('BULKSMS_TOKEN_SECRET', '')
BULKSMS_TEST_PHONE_NUMBER = os.environ.get('BULKSMS_TEST_PHONE_NUMBER', '')
BULKSMS_PUBLIC_URL = os.environ.get('BULKSMS_PUBLIC_URL', '').rstrip('/')

# Password-reset email. Console mode is safe for local development; select
# SMTP explicitly when testing delivery through Mailtrap.
EMAIL_MODE = os.environ.get('EMAIL_MODE', 'console').strip().lower()
if EMAIL_MODE not in ('console', 'smtp'):
    raise ImproperlyConfigured("EMAIL_MODE must be either 'console' or 'smtp'.")

EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_MODE == 'smtp'
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'live.smtp.mailtrap.io')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = _environment_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'api')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'Neighbourhood Alert <noreply@localhost>',
)

if EMAIL_MODE == 'smtp':
    missing_email_settings = [
        name
        for name, value in (
            ('EMAIL_HOST_PASSWORD', EMAIL_HOST_PASSWORD),
            ('DEFAULT_FROM_EMAIL', os.environ.get('DEFAULT_FROM_EMAIL', '')),
        )
        if not value
    ]
    if missing_email_settings:
        raise ImproperlyConfigured(
            'Set the required SMTP environment variable(s): '
            + ', '.join(missing_email_settings)
        )

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Login redirect URL
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

# Messages
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Session settings
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
