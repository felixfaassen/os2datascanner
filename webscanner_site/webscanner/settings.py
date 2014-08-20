"""
Django settings for webscanner project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
VAR_DIR = os.path.join(PROJECT_DIR, 'var')
LOGS_DIR = os.path.join(VAR_DIR, 'logs')

# Site URL for calculating absolute URLs in emails.
SITE_URL = 'http://webscanner.magenta-aps.dk'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ld0_g)jhp3v27&od88-_v83ldb!0i^bac=jh+je!!=jbvra7@j'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'os2webscanner',
    'recurrence',
    'django_xmlrpc',
)

XMLRPC_METHODS = (
    ('os2webscanner.views.scan_urls', 'scan_urls'),
    ('os2webscanner.views.scan_documents', 'scan_documents'),
)
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'webscanner.urls'

WSGI_APPLICATION = 'webscanner.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'os2webscanner',
        'USER': 'os2webscanner',
        'PASSWORD': 'os2webscanner',
        'HOST': '127.0.0.1',
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'da-dk'

TIME_ZONE = 'CET'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/home/os2/os2webscanner/webscanner_site/static'

AUTH_PROFILE_MODULE = 'os2webscanner.UserProfile'

LOGIN_REDIRECT_URL = '/'

# Email settings

DEFAULT_FROM_EMAIL = 'carstena@magenta.dk'
ADMIN_EMAIL = 'carstena@magenta.dk'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 25
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

local_settings_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'local_settings.py'
)
if os.path.exists(local_settings_file):
    from local_settings import *
