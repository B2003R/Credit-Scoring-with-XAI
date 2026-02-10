import mlflow.lightgbm
import pandas as pd
import shap
import uvicorn
import logging
import os
import math
from fastapi import FastAPI, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Dict
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Use environment variable with fallback to Docker container path
LOCAL_MODEL_PATH = os.getenv("MODEL_PATH", "/app/model_dir")
API_KEY = os.getenv("API_KEY", None)  # Set to None to disable auth in dev
MAX_FEATURES = 300  # Prevent DoS attacks

# Security: API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Global variables
ml_models = {}

# Define expected feature set (will be populated at startup)
expected_features = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    global expected_features
    logger.info(f"Loading model from path: {LOCAL_MODEL_PATH}")
    
    try:
        # Load model directly from the folder we copied
        model = mlflow.lightgbm.load_model(LOCAL_MODEL_PATH)
        
        # Initialize SHAP
        logger.info("Initializing SHAP Explainer...")
        explainer = shap.TreeExplainer(model)
        
        # Store expected feature names
        if hasattr(model, 'feature_name_'):
            expected_features = set(model.feature_name_)
            logger.info(f"Loaded {len(expected_features)} expected features")
        
        # Store in global dictionary
        ml_models["model"] = model
        ml_models["explainer"] = explainer
        
        logger.info("Model and explainer loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        raise
    
    yield
    
    # --- SHUTDOWN LOGIC ---
    logger.info("Shutting down application...")
    ml_models.clear()

app = FastAPI(title="Credit Scoring XAI Service", lifespan=lifespan)

# Add security headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Authentication dependency
async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key if authentication is enabled"""
    if API_KEY is None:
        # Authentication disabled for development
        return None
    if api_key is None or api_key != API_KEY:
        logger.warning("Unauthorized access attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key"
        )
    return api_key

class CustomerData(BaseModel):
    features: Dict[str, float] = Field(
        ..., 
        max_length=MAX_FEATURES,
        description="Customer features for credit scoring"
    )
    
    @field_validator('features')
    @classmethod
    def validate_features(cls, v):
        """Validate feature dictionary"""
        if not v:
            raise ValueError("Features dictionary cannot be empty")
        
        if len(v) > MAX_FEATURES:
            raise ValueError(f"Too many features provided. Maximum allowed: {MAX_FEATURES}")
        
        # Validate all values are numeric and not NaN/Inf
        for key, value in v.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"Feature '{key}' must be numeric")
            # Check for NaN and Inf values (booleans are excluded from this check)
            if not isinstance(value, bool):
                if math.isnan(value) or math.isinf(value):
                    raise ValueError(f"Feature '{key}' has invalid value (NaN or Inf)")
        
        return v

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "model_loaded": "model" in ml_models,
        "explainer_loaded": "explainer" in ml_models
    }

@app.post("/predict")
async def predict_credit_risk(
    data: CustomerData,
    api_key: str = Security(verify_api_key)
):
    """
    Predict credit risk for a customer
    
    Security features:
    - API key authentication (if enabled via API_KEY env var)
    - Input validation and sanitization
    - Rate limiting (recommended to add via middleware)
    - Generic error messages
    """
    try:
        model = ml_models.get("model")
        explainer = ml_models.get("explainer")
        
        if not model or not explainer:
            logger.error("Model or explainer not loaded")
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable"
            )
        
        # Create DataFrame from validated features
        input_df = pd.DataFrame([data.features])
        
        # Log prediction request (without sensitive data)
        logger.info(f"Processing prediction request with {len(data.features)} features")
        
        # 1. Generate Prediction
        prob_default = model.predict_proba(input_df)[0][1]
        decision = "REJECT" if prob_default > 0.5 else "APPROVE"
        
        # 2. Generate SHAP explanations
        shap_values = explainer.shap_values(input_df)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
            
        feature_importance = dict(zip(input_df.columns, shap_values[0]))
        top_factors = sorted(
            feature_importance.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )[:5]

        logger.info(f"Prediction completed: {decision} (score: {prob_default:.3f})")
        
        return {
            "decision": decision,
            "risk_score": float(prob_default),
            "top_risk_factors": top_factors
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        # Input validation errors
        logger.warning(f"Input validation error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid input data")
    except Exception as e:
        # Log detailed error internally, return generic message
        logger.error(f"Prediction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request"
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)