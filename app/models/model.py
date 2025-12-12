from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialise SQLAlchemy
db = SQLAlchemy()

""" class logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(255), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Integer, nullable=False)
    fat = db.Column(db.Integer, nullable=False)
    carbohydrates = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now) """
    
class Food(db.Model):
    __tablename__ = 'foods'
    
    id = db.Column(db.String, primary_key=True)  
    name = db.Column(db.String, nullable=False)
    category_name = db.Column(db.String, nullable=False)
    brand_name = db.Column(db.String)
    serving_size_g = db.Column(db.Float)
    serving_size_ml = db.Column(db.Float)
    calories = db.Column(db.Float)
    protein_g = db.Column(db.Float)
    carbs_g = db.Column(db.Float)
    fat_g = db.Column(db.Float)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category_name": self.category_name,
            "brand_name": self.brand_name,
            "serving_size_g": self.serving_size_g,
            "serving_size_ml": self.serving_size_ml,
            "calories": self.calories,
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
        }