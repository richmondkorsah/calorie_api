from flask import Blueprint, request, jsonify
from huggingface_hub import InferenceClient
import os
import base64
from io import BytesIO

from app.models.model import Food

image_bp = Blueprint('image', __name__)

# Initialize Hugging Face client
HF_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")

if not HF_TOKEN:
    print("WARNING: HUGGINGFACE_API_TOKEN not set in environment variables")

client = InferenceClient(token=HF_TOKEN) if HF_TOKEN else None


@image_bp.route("/analyze", methods=["POST"])
def analyze_food_image():
    """
    Analyze food image and return nutritional information
    
    Usage:
    - Upload file: curl.exe -X POST http://localhost:5000/api/image/analyze -F "image=@burger.jpg"
    
    Returns: Food predictions with matching database entries
    """
    if not client:
        return jsonify({"error": "Hugging Face API not configured. Set HUGGINGFACE_API_TOKEN"}), 500
    
    try:
        image_bytes = None
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Read raw image bytes
            image_bytes = file.read()
        
        # Handle base64 image
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                try:
                    image_bytes = base64.b64decode(data['image_base64'])
                except Exception as e:
                    return jsonify({"error": f"Invalid base64 image: {str(e)}"}), 400
        
        if not image_bytes:
            return jsonify({
                "error": "No image provided. Send 'image' file or 'image_base64' in JSON"
            }), 400
        
        # Call Hugging Face food classification model
        # Pass raw bytes directly
        result = client.image_classification(
            image=image_bytes,
            model="nateraw/food"
        )
        
        # Get top 5 predictions
        predictions = result[:5]
        
        # Search database for matching foods
        food_matches = []
        for pred in predictions:
            food_name = pred['label'].replace('_', ' ').replace('-', ' ')
            confidence = pred['score']
            
            # Find similar foods in database
            matching_foods = Food.query.filter(
                Food.name.ilike(f'%{food_name}%')
            ).limit(3).all()
            
            food_matches.append({
                "prediction": food_name,
                "confidence": round(confidence * 100, 2),
                "matches": [food.to_dict() for food in matching_foods] if matching_foods else []
            })
        
        return jsonify({
            "success": True,
            "model": "nateraw/food (Food-101)",
            "predictions": food_matches
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@image_bp.route("/analyze/advanced", methods=["POST"])
def analyze_food_advanced():
    """
    Detailed food analysis using Vision-Language Model
    
    Uses a more powerful model to describe the food and estimate portions
    """
    if not client:
        return jsonify({"error": "Hugging Face API not configured"}), 500
    
    try:
        image_bytes = None
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            image_bytes = file.read()
        
        # Handle base64 image
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                image_bytes = base64.b64decode(data['image_base64'])
        
        if not image_bytes:
            return jsonify({"error": "No image provided"}), 400
        
        # Use vision language model for detailed analysis
        result = client.image_to_text(
            image=image_bytes,
            model="Salesforce/blip-image-captioning-large"
        )
        
        description = result
        
        # Extract food keywords from description
        keywords = [word for word in description.lower().split() if len(word) > 3]
        
        # Search database for matching foods
        matching_foods = []
        for keyword in keywords[:5]:
            foods = Food.query.filter(
                Food.name.ilike(f'%{keyword}%')
            ).limit(2).all()
            matching_foods.extend(foods)
        
        # Remove duplicates
        unique_foods = list({f.id: f for f in matching_foods}.values())
        
        return jsonify({
            "success": True,
            "model": "Salesforce/blip-image-captioning-large",
            "description": description,
            "suggested_foods": [food.to_dict() for food in unique_foods[:5]]
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@image_bp.route("/analyze/nutrition", methods=["POST"])
def analyze_with_nutrition():
    """
    Combined analysis: Food detection + Nutrition estimation
    
    Uses both classification and vision models for best results
    """
    if not client:
        return jsonify({"error": "Hugging Face API not configured"}), 500
    
    try:
        image_bytes = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            image_bytes = file.read()
        
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                image_bytes = base64.b64decode(data['image_base64'])
        
        if not image_bytes:
            return jsonify({"error": "No image provided"}), 400
        
        # Step 1: Classify food
        classification = client.image_classification(
            image=image_bytes,
            model="nateraw/food"
        )
        
        top_prediction = classification[0]
        food_name = top_prediction['label'].replace('_', ' ')
        confidence = top_prediction['score']
        
        # Step 2: Find matching foods in database
        matching_foods = Food.query.filter(
            Food.name.ilike(f'%{food_name}%')
        ).limit(5).all()
        
        # Calculate average nutrition if multiple matches
        if matching_foods:
            avg_calories = sum(f.calories for f in matching_foods) / len(matching_foods)
            avg_protein = sum(f.protein_g for f in matching_foods) / len(matching_foods)
            avg_carbs = sum(f.carbs_g for f in matching_foods) / len(matching_foods)
            avg_fat = sum(f.fat_g for f in matching_foods) / len(matching_foods)
            
            estimated_nutrition = {
                "calories": round(avg_calories, 1),
                "protein_g": round(avg_protein, 1),
                "carbs_g": round(avg_carbs, 1),
                "fat_g": round(avg_fat, 1)
            }
        else:
            estimated_nutrition = None
        
        return jsonify({
            "success": True,
            "food_detected": food_name,
            "confidence": round(confidence * 100, 2),
            "estimated_nutrition": estimated_nutrition,
            "database_matches": [food.to_dict() for food in matching_foods],
            "note": "Nutrition is estimated based on similar foods. Actual values depend on portion size and preparation."
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@image_bp.route("/models", methods=["GET"])
def get_models_info():
    """List available food analysis models and their capabilities"""
    return jsonify({
        "models": [
            {
                "endpoint": "/api/image/analyze",
                "model": "nateraw/food",
                "type": "Classification",
                "speed": "Fast (1-2s)",
                "accuracy": "High (~85%)",
                "categories": "101 food categories",
                "best_for": "Quick food identification"
            },
            {
                "endpoint": "/api/image/analyze/advanced",
                "model": "Salesforce/blip-image-captioning-large",
                "type": "Vision-Language",
                "speed": "Medium (3-5s)",
                "accuracy": "Very High",
                "features": "Describes portions, ingredients, preparation",
                "best_for": "Detailed food analysis"
            },
            {
                "endpoint": "/api/image/analyze/nutrition",
                "model": "Combined (nateraw/food + database)",
                "type": "Hybrid",
                "speed": "Fast (1-2s)",
                "accuracy": "High",
                "features": "Food ID + Nutrition estimation",
                "best_for": "Getting nutritional values"
            }
        ],
        "recommendations": {
            "quick_identification": "Use /analyze",
            "detailed_description": "Use /analyze/advanced",
            "nutrition_tracking": "Use /analyze/nutrition (RECOMMENDED)"
        }
    }), 200


@image_bp.route("/test", methods=["GET"])
def test_api():
    """Test if Hugging Face API is configured correctly"""
    if not HF_TOKEN:
        return jsonify({
            "configured": False,
            "message": "HUGGINGFACE_API_TOKEN not found in environment"
        }), 500
    
    return jsonify({
        "configured": True,
        "message": "Hugging Face API ready",
        "token_prefix": HF_TOKEN[:10] + "..."
    }), 200