"""WSGI entry point: waitress-serve fiteval_app.wsgi:server"""

import os

from .app import create_app

server = create_app(url_prefix=os.environ.get("FITEVAL_URL_PREFIX")).server
