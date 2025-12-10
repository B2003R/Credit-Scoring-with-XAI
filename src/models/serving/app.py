import mlflow.lightgbm
import pandas as pd
import shap
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from contextlib import asynccontextmanager

# --- CONFIGURATION ---
# We now point to the folder inside the Docker container
LOCAL_MODEL_PATH = "/app/model_dir"

# Global variables
ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP LOGIC ---
    print(f"Loading model from local path: {LOCAL_MODEL_PATH}...")
    
    # Load model directly from the folder we copied
    model = mlflow.lightgbm.load_model(LOCAL_MODEL_PATH)
    
    # Initialize SHAP
    print("Initializing SHAP Explainer...")
    explainer = shap.TreeExplainer(model)
    
    # Store in global dictionary
    ml_models["model"] = model
    ml_models["explainer"] = explainer
    
    yield
    
    # --- SHUTDOWN LOGIC ---
    ml_models.clear()

app = FastAPI(title="Credit Scoring XAI Service", lifespan=lifespan)

class CustomerData(BaseModel):
    features: Dict[str, float]

@app.post("/predict")
async def predict_credit_risk(data: CustomerData):
    try:
        model = ml_models["model"]
        explainer = ml_models["explainer"]
        
        input_df = pd.DataFrame([data.features])
        
        # 1. Generate Prediction
        prob_default = model.predict_proba(input_df)[0][1]
        decision = "REJECT" if prob_default > 0.5 else "APPROVE"
        
        # 2. Generate SHAP
        shap_values = explainer.shap_values(input_df)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
            
        feature_importance = dict(zip(input_df.columns, shap_values[0]))
        top_factors = sorted(
            feature_importance.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )[:5]

        return {
            "decision": decision,
            "risk_score": float(prob_default),
            "top_risk_factors": top_factors
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)