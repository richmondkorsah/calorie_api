from flask import Flask
from dotenv import load_dotenv
from .models.model import db

from .route.routes import main_bp
from .route.image import image_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    db.init_app(app)
    
    app.register_blueprint(main_bp, url_prefix="/api")
    app.register_blueprint(image_bp, url_prefix="/api")
    
    
    return app