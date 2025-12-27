from flask import Blueprint, request, jsonify
import os
import base64
from io import BytesIO
from PIL import Image
import logging
import google.generativeai as genai

from app.models.model import Food

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

image_bp = Blueprint('image', __name__)

# Initialize Google Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set in environment variables")
    model = None
    model_name_used = None
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # List available models to find vision-capable ones
        try:
            available_models = genai.list_models()
            vision_models = [
                m.name for m in available_models 
                if 'generateContent' in m.supported_generation_methods
            ]
            logger.info(f"Available vision models: {vision_models}")
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            vision_models = []
        
        # Try known vision model names in order of preference
        model_names = [
            'gemini-1.5-pro',
            'gemini-1.5-flash',
            'gemini-pro-vision',
            'gemini-1.5-pro-latest',
            'gemini-1.5-flash-latest'
        ]
        
        # If we found models from listing, prioritize those
        if vision_models:
            # Extract just the model name without 'models/' prefix
            clean_vision_models = [m.replace('models/', '') for m in vision_models]
            model_names = clean_vision_models + model_names
        
        model = None
        model_name_used = None
        for name in model_names:
            try:
                model = genai.GenerativeModel(name)
                model_name_used = name
                logger.info(f"Google Gemini initialized successfully with {name}")
                break
            except Exception as e:
                logger.debug(f"Failed to initialize with {name}: {e}")
                continue
        
        if not model:
            logger.error("Could not initialize any Gemini model")
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}")
        model = None
        model_name_used = None

# Stopwords for keyword extraction
STOPWORDS = {
    "with", "this", "that", "from", "have", "plate", "table", 
    "white", "black", "food", "bowl", "dish", "served", "there",
    "sitting", "top", "next", "image", "photo", "picture", "shows",
    "contains", "features", "appears", "looks", "like", "here's",
    "analysis", "visible", "estimated", "portion", "size", "approximately",
    "preparation", "method", "main", "items", "ingredients", "single",
    "substantial", "serving", "likely", "similar", "inches", "length"
}

# Constants
MAX_IMAGE_SIZE = (1024, 1024)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_and_process_image(file_source, is_base64=False):
    """Validate and process image from file upload or base64"""
    try:
        if is_base64:
            image_bytes = base64.b64decode(file_source)
        else:
            image_bytes = file_source.read()
        
        if len(image_bytes) > MAX_FILE_SIZE:
            raise ValueError(f"Image too large. Max size: {MAX_FILE_SIZE / (1024*1024)}MB")
        
        image = Image.open(BytesIO(image_bytes))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        if image.size[0] > MAX_IMAGE_SIZE[0] or image.size[1] > MAX_IMAGE_SIZE[1]:
            image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        
        return image
        
    except base64.binascii.Error:
        raise ValueError("Invalid base64 encoding")
    except Exception as e:
        raise ValueError(f"Invalid image: {str(e)}")


def extract_food_keywords(description, min_length=3, max_keywords=10):
    """Extract relevant food keywords from description"""
    # Convert to lowercase and split
    text = description.lower()
    
    # Remove markdown formatting
    text = text.replace('**', '').replace('*', '').replace('#', '')
    
    # Split into words
    words = text.split()
    
    # Extract words that might be food items
    keywords = []
    food_indicators = {'main', 'ingredients', 'items', 'food'}
    
    for i, word in enumerate(words):
        # Clean the word
        clean_word = word.strip('.,!?;:()[]')
        
        # Skip stopwords and very short words
        if clean_word in STOPWORDS or len(clean_word) <= min_length:
            continue
        
        # Skip numbered lists
        if clean_word.isdigit() or clean_word.endswith('.'):
            continue
        
        # Prioritize words after food indicators
        if i > 0 and words[i-1].strip('.,!?;:()[]') in food_indicators:
            keywords.insert(0, clean_word)  # Add to front
        else:
            keywords.append(clean_word)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique_keywords.append(k)
    
    return unique_keywords[:max_keywords]


def search_matching_foods(keywords, limit_per_keyword=3, max_total=8):
    """Search database for foods matching keywords with ranking"""
    food_scores = {}  # Track foods and their relevance scores
    
    for idx, keyword in enumerate(keywords):
        try:
            # Search for foods matching this keyword
            foods = Food.query.filter(
                Food.name.ilike(f'%{keyword}%')
            ).limit(limit_per_keyword).all()
            
            for food in foods:
                food_id = food.id
                
                # Score based on keyword position (earlier = more important)
                position_score = len(keywords) - idx
                
                # Score based on match quality
                food_name_lower = food.name.lower()
                keyword_lower = keyword.lower()
                
                if food_name_lower == keyword_lower:
                    match_score = 10  # Exact match
                elif food_name_lower.startswith(keyword_lower):
                    match_score = 5   # Starts with keyword
                else:
                    match_score = 1   # Contains keyword
                
                total_score = position_score + match_score
                
                # Keep the highest score for each food
                if food_id not in food_scores or food_scores[food_id]['score'] < total_score:
                    food_scores[food_id] = {
                        'food': food,
                        'score': total_score,
                        'keyword': keyword
                    }
        
        except Exception as e:
            logger.error(f"Database query error for keyword '{keyword}': {e}")
    
    # Sort by score (highest first) and return foods
    sorted_foods = sorted(food_scores.values(), key=lambda x: x['score'], reverse=True)
    unique_foods = [item['food'] for item in sorted_foods[:max_total]]
    
    return unique_foods


def analyze_food_with_gemini(image, custom_prompt=None):
    """
    Analyze food image using Google Gemini Vision
    
    Args:
        image: PIL Image object
        custom_prompt: Optional custom prompt
    
    Returns:
        Description string
    """
    if not model:
        raise RuntimeError("Gemini model not initialized. Set GEMINI_API_KEY environment variable.")
    
    try:
        logger.info(f"Analyzing image with Gemini, size: {image.size}")
        
        # Default prompt for food analysis
        if not custom_prompt:
            prompt = """Analyze this food image and provide a concise description.

Focus on:
1. Primary food item name (e.g., "Chicken Caesar Wrap", "Margherita Pizza")
2. Main ingredients visible
3. Portion size (small/medium/large)

Format: Start with the food name, then list ingredients.
Example: "Chicken Caesar Wrap with grilled chicken, romaine lettuce, parmesan cheese, Caesar dressing in a flour tortilla. Medium portion."

Keep it brief and focused on food identification."""
        else:
            prompt = custom_prompt
        
        # Generate response
        response = model.generate_content([prompt, image])
        
        if not response or not response.text:
            raise RuntimeError("Gemini returned empty response")
        
        description = response.text.strip()
        logger.info(f"Generated description: {description}")
        
        return description
        
    except Exception as e:
        logger.error(f"Gemini analysis error: {type(e).__name__}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to analyze image: {str(e)}")


@image_bp.route("/analyze", methods=["POST"])
@image_bp.route("/analyze/vision", methods=["POST"])
def analyze_with_vision_model():
    """Analyze food using Google Gemini Vision"""
    if not model:
        return jsonify({
            "error": "API not configured",
            "message": "GEMINI_API_KEY environment variable not set",
            "setup": "Get your free API key from https://aistudio.google.com/apikey"
        }), 503
    
    try:
        image = None
        custom_prompt = None
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if not file.filename:
                return jsonify({"error": "No file selected"}), 400
            
            custom_prompt = request.form.get('prompt')
            image = validate_and_process_image(file)
        
        # Handle JSON with base64
        elif request.is_json:
            data = request.get_json()
            
            if not data or 'image_base64' not in data:
                return jsonify({"error": "No image_base64 provided in JSON"}), 400
            
            custom_prompt = data.get('prompt')
            image = validate_and_process_image(data['image_base64'], is_base64=True)
        
        else:
            return jsonify({
                "error": "Invalid request format. Use multipart/form-data or JSON with image_base64"
            }), 400
        
        # Analyze with Gemini
        description = analyze_food_with_gemini(image, custom_prompt)
        
        # Extract keywords and search foods
        keywords = extract_food_keywords(description)
        matching_foods = search_matching_foods(keywords)
        
        return jsonify({
            "success": True,
            "model": model_name_used or "gemini-vision",
            "description": description,
            "extracted_keywords": keywords,
            "suggested_foods": [food.to_dict() for food in matching_foods],
            "count": len(matching_foods),
            "tip": "Use the suggested foods with /analyze/nutrition endpoint for detailed nutritional info"
        }), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@image_bp.route("/analyze/advanced", methods=["POST"])
def analyze_food_advanced():
    """Detailed food analysis with nutritional estimation"""
    if not model:
        return jsonify({
            "error": "API not configured",
            "message": "GEMINI_API_KEY environment variable not set"
        }), 503
    
    try:
        image = None
        
        if 'image' in request.files:
            file = request.files['image']
            if not file.filename:
                return jsonify({"error": "No file selected"}), 400
            image = validate_and_process_image(file)
        
        elif request.is_json:
            data = request.get_json()
            if not data or 'image_base64' not in data:
                return jsonify({"error": "No image_base64 provided"}), 400
            image = validate_and_process_image(data['image_base64'], is_base64=True)
        
        else:
            return jsonify({"error": "Invalid request format"}), 400
        
        # Advanced prompt for more details
        advanced_prompt = """Analyze this food image and provide:
        1. Main food items (be specific, e.g., "cheeseburger" not just "burger")
        2. Visible ingredients
        3. Preparation method (fried, grilled, baked, etc.)
        4. Estimated portion size
        
        Be concise and specific about the food items."""
        
        description = analyze_food_with_gemini(image, advanced_prompt)
        
        keywords = extract_food_keywords(description)
        matching_foods = search_matching_foods(keywords)
        
        return jsonify({
            "success": True,
            "model": model_name_used or "gemini-vision",
            "description": description,
            "extracted_keywords": keywords,
            "suggested_foods": [food.to_dict() for food in matching_foods],
            "count": len(matching_foods)
        }), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@image_bp.route("/models", methods=["GET"])
def get_models_info():
    """List available models"""
    return jsonify({
        "models": [
            {
                "name": "gemini-1.5-flash-latest",
                "provider": "Google",
                "type": "Vision-Language Model",
                "speed": "Very Fast (1-2s)",
                "accuracy": "Excellent",
                "features": [
                    "Detailed food description",
                    "Ingredient identification",
                    "Portion estimation",
                    "Preparation method detection"
                ],
                "cost": "Free (15 requests/min, 1500 requests/day)",
                "endpoint": "/api/image/analyze"
            }
        ],
        "setup": {
            "step1": "Get free API key from https://aistudio.google.com/apikey",
            "step2": "Set environment variable: GEMINI_API_KEY=your_key_here",
            "step3": "Install package: pip install google-generativeai"
        }
    }), 200


@image_bp.route("/test", methods=["GET"])
def test_api():
    """Test if Gemini API is configured"""
    if not GEMINI_API_KEY:
        return jsonify({
            "configured": False,
            "status": "error",
            "message": "GEMINI_API_KEY not found in environment",
            "setup": "Get your free key from https://aistudio.google.com/apikey"
        }), 503
    
    if not model:
        return jsonify({
            "configured": False,
            "status": "error",
            "message": "Gemini model initialization failed"
        }), 503
    
    return jsonify({
        "configured": True,
        "status": "ok",
        "message": "Google Gemini Vision API ready",
        "model": model_name_used or "gemini-vision",
        "rate_limits": "15 requests/min, 1500 requests/day (free tier)"
    }), 200


@image_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "image-analysis",
        "api_configured": model is not None,
        "provider": "Google Gemini"
    }), 200