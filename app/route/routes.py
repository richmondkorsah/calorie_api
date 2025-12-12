from flask import Blueprint, jsonify, request
from sqlalchemy import func
import requests

from app.models.model import Food

main_bp = Blueprint('main', __name__)


# This endpoint gets all the foods in the database
# Query parameters: limit (page number), per_page (items per page, max 100)
# Returns: Paginated list of foods with metadata (total, pages, has_next/prev)
@main_bp.route("/foods", methods=["GET"])
def get_all_foods():
    foods = Food.query.all()
    limit = request.args.get("limit", type=int)
    per_page = request.args.get("per_page", 20,type=int)
    
    # Limit per_page to maximum of 100 to prevent excessive queries
    per_page = min(per_page, 100)
    
    pagination = Food.query.paginate(page=limit, per_page=per_page, error_out=False)
    
    """Search the foods and return all the .to_dict() returns the entries as dictionaries"""
    return jsonify({
        "foods": [food.to_dict() for food in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev
    }), 200


# This endpoint gets a specific food by its ID
# Path parameter: id (food identifier)
# Returns: Single food item as dictionary, or 404 if not found
@main_bp.route("/food/<string:id>", methods=["GET"])
def get_food(id):
    # Query database for food with matching ID, returns 404 automatically if not found
    food_id = Food.query.filter_by(id=id).first_or_404()
    """Search for a food by ID and return it as a dictionary"""
    if food_id:
        return jsonify(food_id.to_dict()), 200
    else:
        return jsonify({"error": "Food not found"}), 404
    
    
# This endpoint searches for foods by name using a query parameter
# Query parameter: q (search term, required)
# Returns: List of foods with names matching the search term (case-insensitive)
@main_bp.route("/search", methods=["GET"])
def search_food():
    query = request.args.get("q")
    # Perform case-insensitive search using ilike
    search_result = Food.query.filter(Food.name.ilike(query)).all()
    """Search for foods by name and return all matching results as dictionaries"""
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    if query:
        return jsonify([food.to_dict() for food in search_result]), 200
    else:
        return jsonify({"error": "Food not found"}), 404
    

@main_bp.route("/search/advanced", methods=["GET"])
def advanced_search():
    """Search by name, category, and brand simultaneously"""
    name = request.args.get("name")
    category = request.args.get("category")
    brand = request.args.get("brand")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    
    q = Food.query
    
    if name:
        q = q.filter(Food.name.ilike(f'%{name}%'))
    if category:
        q = q.filter(Food.category_name.ilike(f'%{category}%'))
    if brand:
        q = q.filter(Food.brand_name.ilike(f'%{brand}%'))
    
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "foods": [food.to_dict() for food in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page
    }), 200
  
    
# This endpoint gets all unique food categories from the database
# Returns: Count and list of all distinct category names
@main_bp.route("/category", methods=["GET"])
def get_all_categories():
    # Query only category_name column and get distinct values
    categories = Food.query.with_entities(Food.category_name).distinct().all()
    """Query all distinct categories and return them as a list"""
    # Extract category names from query result tuples
    category_list = [category[0] for category in categories]
    if categories:
        return jsonify({
            "count": len(category_list),
            "categories": category_list
        }), 200
    else:
        return jsonify({"error": "No categories found"}), 404
    

# This endpoint gets all foods in a specific category (case-insensitive partial match)
# Path parameter: category_name (category to filter by)
# Returns: List of foods in the specified category
@main_bp.route("/category/<string:category_name>", methods=["GET"])
def get_category(category_name):
    # Use ilike for case-insensitive partial matching with wildcards
    get_category_name = Food.query.filter(Food.category_name.ilike(f'%{category_name}%')).all()
    """Filter foods by category name and return all matching foods as dictionaries"""
    if get_category_name:
        return jsonify([category_name.to_dict() for category_name in get_category_name]), 200
    else:
        return jsonify({"error": "category not found"}), 404
    

# This endpoint gets all unique brand names from the database
# Returns: Count and list of all distinct brand names
@main_bp.route("/brands", methods=["GET"])
def get_all_brands():
    # Query only brand_name column and get distinct values
    brands = Food.query.with_entities(Food.brand_name).distinct().all()
    """Query all distinct brand names and return them as a list"""
    # Extract brand names from query result tuples
    brand_list = [brand[0] for brand in brands]
    if brands:
        return jsonify({
            "count": len(brand_list),
            "brands": brand_list
        }), 200
    else:
        return jsonify({"error": "No brands found"}), 404
    

# This endpoint gets all foods from a specific brand (case-insensitive partial match)
# Path parameter: brand_name (brand to filter by)
# Returns: List of foods from the specified brand
@main_bp.route("/brands/<string:brand_name>", methods=["GET"])
def get_brand(brand_name):
    # Use ilike for case-insensitive partial matching with wildcards
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


# This endpoint returns a random food item from the database
# Returns: Single random food item as dictionary
@main_bp.route("/random", methods=["GET"])
def get_random_food():
    """Get a random food item from the database and return it as a dictionary"""
    # Use SQL random() function to get a random row
    random_food = Food.query.order_by(func.random()).first()
    if random_food:
        return jsonify(random_food.to_dict()), 200
    else:
        return jsonify({"error": "Couldn't return an item from the database"}), 404
    
    
# Get highest protein foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by protein content (highest first)
@main_bp.route("/top/protein", methods=["GET"])
def get_top_protein():
    """Get top foods by protein content"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    top_foods = Food.query.order_by(Food.protein_g.desc()).limit(limit).all()
    
    return jsonify([food.to_dict() for food in top_foods]), 200


# Get high calorie foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by calorie content (highest first)
@main_bp.route("/top/high-calorie", methods=["GET"])
def get_high_calorie():
    """Get highest calorie foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    high_cal_foods = Food.query.order_by(Food.calories.desc()).limit(limit).all()
    
    return jsonify([food.to_dict() for food in high_cal_foods]), 200


# Get highest fat foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by fat content (highest first)
@main_bp.route("/top/high-fat", methods=["GET"])
def get_high_fat():
    """Get highest fat foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    high_fat_foods = Food.query.order_by(Food.fat_g.desc()).limit(limit).all()

    return jsonify([food.to_dict() for food in high_fat_foods]), 200


# Get highest carb foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by carbohydrate content (highest first)
@main_bp.route("/top/high-carbs", methods=["GET"])
def get_high_carbs():
    """Get highest carbohydrate foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    high_carb_foods = Food.query.order_by(Food.carbs_g.desc()).limit(limit).all()

    return jsonify([food.to_dict() for food in high_carb_foods]), 200

# Lowest protein foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by protein content (lowest first)
@main_bp.route("/top/low-protein", methods=["GET"])
def get_low_protein():
    """Get lowest protein foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    low_protein_foods = Food.query.order_by(Food.protein_g.asc()).limit(limit).all()
    return jsonify([food.to_dict() for food in low_protein_foods]), 200

# Lowest calorie foods
@main_bp.route("/top/low-calorie", methods=["GET"])
def get_low_calorie():
    limit = request.args.get("limit", 10, type=int)
    low_cal_foods = Food.query.order_by(Food.calories.asc()).limit(limit).all()
    return jsonify([food.to_dict() for food in low_cal_foods]), 200

# Lowest fat foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by fat content (lowest first)
@main_bp.route("/top/low-fat", methods=["GET"])
def get_low_fat():
    """Get lowest fat foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    low_fat_foods = Food.query.order_by(Food.fat_g.asc()).limit(limit).all()
    return jsonify([food.to_dict() for food in low_fat_foods]), 200

# Lowest carbs foods
# Query parameter: limit (number of results, default 10)
# Returns: List of foods sorted by carbohydrate content (lowest first)
@main_bp.route("/top/low-carbs", methods=["GET"])
def get_low_carbs():
    """Get lowest carbohydrate foods"""
    # Get limit parameter with default of 10
    limit = request.args.get("limit", 10, type=int)
    low_carb_foods = Food.query.order_by(Food.carbs_g.asc()).limit(limit).all()
    return jsonify([food.to_dict() for food in low_carb_foods]), 200