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
        return jsonify([food.to_dict() for food in search_result]), 200
    else:
        return jsonify({"error": "Food not found"}), 404
    
    
# This endpoint gets all unique food categories from the database
@main_bp.route("/category", methods=["GET"])
def get_all_categories():
    categories = Food.query.with_entities(Food.category_name).distinct().all()
    """Query all distinct categories and return them as a list"""
    category_list = [category[0] for category in categories]
    if categories:
        return jsonify({
            "count": len(category_list),
            "categories": category_list
        }), 200
    else:
        return jsonify({"error": "No categories found"}), 404
    

# This endpoint gets all foods in a specific category (case-insensitive partial match)
@main_bp.route("/category/<string:category_name>", methods=["GET"])
def get_category(category_name):
    get_category_name = Food.query.filter(Food.category_name.ilike(f'%{category_name}%')).all()
    """Filter foods by category name and return all matching foods as dictionaries"""
    if get_category_name:
        return jsonify([category_name.to_dict() for category_name in get_category_name]), 200
    else:
        return jsonify({"error": "category not found"}), 404
    

# This endpoint gets all unique brand names from the database
@main_bp.route("/brands", methods=["GET"])
def get_all_brands():
    brands = Food.query.with_entities(Food.brand_name).distinct().all()
    """Query all distinct brand names and return them as a list"""
    brand_list = [brand[0] for brand in brands]
    if brands:
        return jsonify({
            "count": len(brand_list),
            "brands": brand_list
        }), 200
    else:
        return jsonify({"error": "No brands found"}), 404
    

# This endpoint gets all foods from a specific brand (case-insensitive partial match)
@main_bp.route("/brands/<string:brand_name>", methods=["GET"])
def get_brand(brand_name):
    get_brand_name = Food.query.filter(Food.brand_name.ilike(f'%{brand_name}%')).all()
    """Filter foods by brand name and return all matching foods as dictionaries"""
    if get_brand_name:
        return jsonify([brand_name.to_dict() for brand_name in get_brand_name]), 200
    else:
        return jsonify({"error": "brand not found"}), 404
    

# This endpoint filters foods by nutritional values using query parameters
@main_bp.route("/filter", methods=["GET"])
def filter():
    """Filter foods by calories, serving size, protein, carbs, and fat ranges. Returns matching foods as dictionaries"""
    q = Food.query
    
    # Filter by calories
    max_cal = request.args.get("max_cal", type=float)
    min_cal = request.args.get("min_cal", type=float)
    
    if max_cal is not None:
        q = q.filter(Food.calories <= max_cal)
    if min_cal is not None:
        q = q.filter(Food.calories >= min_cal)
    
    # Filter by serving size
    max_serving_size = request.args.get("max_ss", type=float)
    min_serving_size = request.args.get("min_ss", type=float)
    
    if max_serving_size is not None:
        q = q.filter(Food.serving_size <= max_serving_size)
    if min_serving_size is not None:
        q = q.filter(Food.serving_size >= min_serving_size)
    
    # Filter by protein
    max_protein = request.args.get("max_protein", type=float)
    min_protein = request.args.get("min_protein", type=float)
    
    if max_protein is not None:
        q = q.filter(Food.protein_g <= max_protein)
    if min_protein is not None:
        q = q.filter(Food.protein_g >= min_protein)
    
    # Filter by carbohydrates
    max_carbs = request.args.get("max_carbs", type=float)
    min_carbs = request.args.get("min_carbs", type=float)
    
    if max_carbs is not None:
        q = q.filter(Food.carbs_g <= max_carbs)
    if min_carbs is not None:
        q = q.filter(Food.carbs_g >= min_carbs)
    
    # Filter by fat
    max_fat = request.args.get("max_fat", type=float)
    min_fat = request.args.get("min_fat", type=float)
    
    if max_fat is not None:
        q = q.filter(Food.fat_g <= max_fat)
    if min_fat is not None:
        q = q.filter(Food.fat_g >= min_fat)
    
    # Limit the number of results
    page_limit = request.args.get("limit", type=int)
    if page_limit is not None:
        q = q.limit(page_limit)
    
    # Execute query and return results
    results = q.all()
    return jsonify([food.to_dict() for food in results]), 200