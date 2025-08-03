# /var/www/optin_app/wsgi.py
import sys
import os

# Tambahkan direktori proyek ke Python path
sys.path.insert(0, '/var/www/mltfreedom')

# Impor objek `app` dari file `app.py`
from app import app as application