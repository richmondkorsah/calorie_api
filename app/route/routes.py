from flask import Blueprint, jsonify, request
import requests

from app.models.model import Food

main_bp = Blueprint('main', __name__)


# This endpoints gets all the foods in the database
@main_bp.route("/foods", methods=["GET"])
def get_all_foods():
    foods = Food.query.all()
    """Search the foods and return all the .to_dict() returns the entries as dictionaries"""
    return jsonify([food.to_dict() for food in foods])


# This endpoint gets a specific food by its ID
@main_bp.route("/food/<string:id>", methods=["GET"])
def get_food(id):
    food_id = Food.query.filter_by(id=id).first_or_404()
    """Search for a food by ID and return it as a dictionary"""
    if food_id:
        return jsonify(food_id.to_dict()), 200
    else:
        return jsonify({"error": "Food not found"}), 404
    
    
# This endpoint searches for foods by name using a query parameter
@main_bp.route("/search", methods=["GET"])
def search_food():
    query = request.args.get("q")
    search_result = Food.query.filter(Food.name.ilike(query)).all()
    """Search for foods by name and return all matching results as dictionaries"""
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    if query:
        return jsonify([food.to_dict() for food in search_result])
    else:
        return jsonify({"error": "Food not found"})
    
    
# This endpoint gets all unique food categories from the database
@main_bp.route("/category", methods=["GET"])
def get_all_categories():
    categories = Food.query.with_entities(Food.category_name).distinct().all()
    """Query all distinct categories and return them as a list"""
    category_list = [category[0] for category in categories]
    return jsonify({
        "count": len(category_list),
        "categories": category_list
    })