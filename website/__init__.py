from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv
import os

from datetime import timedelta

from .fancy.froutes import fancy
from .navaratri.nroutes import navaratri
from .general.groutes import general


load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get("key")
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=60)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max payload

    from .views import views
    from .auth import auth  
    from .general.security import apply_security_headers, apply_cors_headers

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(fancy, url_prefix='/')
    app.register_blueprint(navaratri, url_prefix='/')
    app.register_blueprint(general, url_prefix='/')

    @app.after_request
    def security_middleware(response):
        response = apply_security_headers(response)
        response = apply_cors_headers(response)
        return response

    return app