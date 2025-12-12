from flask import Blueprint, jsonify, request
from sqlalchemy import func


from app.models.model import Food

batch_bp = Blueprint('batch', __name__)


@batch_bp.route("/foods/batch", methods=["POST"])
def get_foods_batch():
    data = request.get_json()
    foods_ids = data.get("ids", [])
    
    if not foods_ids:
        return jsonify({"error": "No food IDs provided"}), 400
    
    foods = Food.query.filter(Food.id.in_(foods_ids)).all()
    
    return jsonify([food.to_dict() for food in foods]), 200
