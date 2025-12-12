from flask import Blueprint, jsonify, request
from sqlalchemy import func
import requests

from app.models.model import Food
from app import db

stat_bp = Blueprint('stats', __name__)


@stat_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get overall statistics about the foods in the database"""
    total_foods = Food.query.count()
    avg_calories = db.session.query(func.round(func.avg(Food.calories), 2)).scalar()
    max_calories = db.session.query(func.max(Food.calories)).scalar()
    min_calories = db.session.query(func.min(Food.calories)).scalar()
    
    return jsonify({
        "total foods": total_foods,
        "average calories": avg_calories,
        "highest calories": max_calories,
        "lowest calories": min_calories
    }), 200
    
    

@stat_bp.route("/stat/categories", methods=["GET"])
def get_categories_stats():
    stats = db.session.query(
        Food.category_name,
        func.count(Food.id).label("count"),
        func.avg(Food.calories).label("average_calories"),
        func.max(Food.calories).label("highest_calories"),
        func.min(Food.calories).label("lowest_calories")
    ).group_by(Food.category_name).all()
    
    return jsonify([{
        "category": stat[0],
        "food_count": stat[1],
        "avg_calories": round(stat[2], 2) if stat[2] else 0,
        "max_calories": stat[3],
        "min_calories": stat[4]
    } for stat in stats]), 200
    