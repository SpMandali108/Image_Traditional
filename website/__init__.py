from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv
import os

from .fancy.froutes import fancy
from .navaratri.nroutes import navaratri
from .general.groutes import general
from website.chatbot.chat import chatbot

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get("key")

    from .views import views
    from .auth import auth  

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(fancy,url_prefix='/')
    app.register_blueprint(navaratri,url_prefix='/')
    app.register_blueprint(general,url_prefix='/')
    app.register_blueprint(chatbot,url_prefix = '/')

   
    return app