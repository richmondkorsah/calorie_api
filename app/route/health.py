from flask import Blueprint, jsonify, request
from sqlalchemy import func
from app.models.model import Food
from app import db


health_bp = Blueprint('health', __name__)

@health_bp.route("/health", methods=["GET"])
def health_check():
    try:
        Food.query.first()
        db_status = "healthy"
    except Exception as e:
        db_status = "unhealthy"
        
    return jsonify({
        "status": "ok" if db_status == "healthy" else "error",
        "database": db_status,
        "version": "1.0.0"
    }), 200 if db_status == "healthy" else 503