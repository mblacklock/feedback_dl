# core/settings/prod.py
from .base import *

DEBUG = False
RUBRIC_MODE = True
ALLOWED_HOSTS = ['mblacklock.pythonanywhere.com']

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-@4egzz4rm--gqesxb#f013#7(h!2t226s(-70f5y0vxj$fmths'