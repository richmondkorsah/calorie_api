from flask import Blueprint, request, jsonify
from huggingface_hub import InferenceClient
import os
import base64
from io import BytesIO
from PIL import Image

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
            
            # Read and convert to PNG format
            try:
                raw_bytes = file.read()
                img = Image.open(BytesIO(raw_bytes))
                
                # Convert to PNG in memory
                img_io = BytesIO()
                img.save(img_io, format='PNG')
                image_bytes = img_io.getvalue()
            except Exception as img_error:
                return jsonify({"error": f"Invalid image file: {str(img_error)}"}), 400
        
        # Handle base64 image
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                try:
                    raw_bytes = base64.b64decode(data['image_base64'])
                    img = Image.open(BytesIO(raw_bytes))
                    
                    # Convert to PNG
                    img_io = BytesIO()
                    img.save(img_io, format='PNG')
                    image_bytes = img_io.getvalue()
                except Exception as e:
                    return jsonify({"error": f"Invalid base64 image: {str(e)}"}), 400
        
        if not image_bytes:
            return jsonify({
                "error": "No image provided. Send 'image' file or 'image_base64' in JSON"
            }), 400
        
        # Call Hugging Face food classification model
        try:
            result = client.image_classification(
                image=image_bytes,
                model="nateraw/food"
            )
        except Exception as model_error:
            return jsonify({
                "error": "Model inference failed",
                "details": str(model_error),
                "suggestion": "Check API token and model availability"
            }), 503
        
        # Get top 5 predictions
        if not result or len(result) == 0:
            return jsonify({"error": "No predictions returned from model"}), 500
            
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
        image_input = None
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            try:
                file.seek(0)
                image_data = Image.open(file.stream)
                image_data.verify()
                file.seek(0)
                image_input = file.stream
            except Exception as img_error:
                return jsonify({"error": f"Invalid image file: {str(img_error)}"}), 400
        
        # Handle base64 image
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                try:
                    image_bytes = base64.b64decode(data['image_base64'])
                    image_data = Image.open(BytesIO(image_bytes))
                    image_data.verify()
                    image_input = BytesIO(image_bytes)
                except Exception as e:
                    return jsonify({"error": f"Invalid base64 image: {str(e)}"}), 400
        
        if not image_input:
            return jsonify({"error": "No image provided"}), 400
        
        # Use vision language model for detailed analysis
        try:
            result = client.image_to_text(
                image=image_input,
                model="Salesforce/blip-image-captioning-large"
            )
        except Exception as model_error:
            return jsonify({
                "error": "Vision model inference failed",
                "details": str(model_error)
            }), 503
        
        description = result if result else "Unable to generate description"
        
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
        image_input = None
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            try:
                file.seek(0)
                image_data = Image.open(file.stream)
                image_data.verify()
                file.seek(0)
                image_input = file.stream
            except Exception as img_error:
                return jsonify({"error": f"Invalid image file: {str(img_error)}"}), 400
        
        elif request.is_json:
            data = request.get_json()
            if 'image_base64' in data:
                try:
                    image_bytes = base64.b64decode(data['image_base64'])
                    image_data = Image.open(BytesIO(image_bytes))
                    image_data.verify()
                    image_input = BytesIO(image_bytes)
                except Exception as e:
                    return jsonify({"error": f"Invalid base64 image: {str(e)}"}), 400
        
        if not image_input:
            return jsonify({"error": "No image provided"}), 400
        
        # Step 1: Classify food
        try:
            classification = client.image_classification(
                image=image_input,
                model="nateraw/food"
            )
        except Exception as model_error:
            return jsonify({
                "error": "Classification failed",
                "details": str(model_error)
            }), 503
        
        if not classification or len(classification) == 0:
            return jsonify({"error": "No food detected in image"}), 404
            
        top_prediction = classification[0]
        food_name = top_prediction['label'].replace('_', ' ')
        confidence = top_prediction['score']
        
        # Step 2: Find matching foods in database
        matching_foods = Food.query.filter(
            Food.name.ilike(f'%{food_name}%')
        ).limit(5).all()
        
        # Calculate average nutrition if multiple matches
        if matching_foods and len(matching_foods) > 0:
            # Filter out None values before calculating averages
            valid_calories = [f.calories for f in matching_foods if f.calories is not None]
            valid_protein = [f.protein_g for f in matching_foods if f.protein_g is not None]
            valid_carbs = [f.carbs_g for f in matching_foods if f.carbs_g is not None]
            valid_fat = [f.fat_g for f in matching_foods if f.fat_g is not None]
            
            avg_calories = sum(valid_calories) / len(valid_calories) if valid_calories else 0
            avg_protein = sum(valid_protein) / len(valid_protein) if valid_protein else 0
            avg_carbs = sum(valid_carbs) / len(valid_carbs) if valid_carbs else 0
            avg_fat = sum(valid_fat) / len(valid_fat) if valid_fat else 0
            
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