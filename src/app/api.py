from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from src.prediction.predictor import Predictor
from src.prediction.spec_coach import coach_spec

app = FastAPI(title="Hybrid AI Product Success Predictor API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PHYSICAL_CATEGORIES = ["wireless_headphones", "bluetooth_speakers", "ice_makers",
                       "smartwatches", "power_banks"]
APP_CATEGORIES: list[str] = []  # apps removed from the system

PROFILES_PATH = ROOT_DIR / "data/extracted/category_profiles.json"

class PredictRequest(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., ge=0.0)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    mock: bool = False

class CoachRequest(BaseModel):
    price: float = Field(..., ge=0.0)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    mock: bool = False

@app.get("/api/categories")
def get_categories():
    return {
        "physical": PHYSICAL_CATEGORIES,
        "app": APP_CATEGORIES
    }

@app.get("/api/profile/{category}")
def get_profile(category: str):
    if not PROFILES_PATH.exists():
        raise HTTPException(status_code=500, detail="Category profiles not found. Run training pipeline first.")
    
    with open(PROFILES_PATH, encoding="utf-8") as f:
        profiles = json.load(f)
        
    if category not in profiles:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found.")
        
    return profiles[category]

@app.get("/api/analyzer")
def get_analyzer_report():
    report_path = ROOT_DIR / "models/training_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=500, detail="Training report not found. Run training pipeline first.")
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/predict")
def predict_success(req: PredictRequest):
    try:
        predictor = Predictor(use_mock_llm=req.mock)
        specs = {
            "name": req.name,
            "price": req.price,
            "description": req.description.strip()
        }
        result = predictor.predict(specs, req.category)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/coach")
def coach_specification(req: CoachRequest):
    try:
        if not PROFILES_PATH.exists():
            raise HTTPException(status_code=500, detail="Category profiles not found. Run training pipeline first.")
        
        with open(PROFILES_PATH, encoding="utf-8") as f:
            profiles = json.load(f)
            
        if req.category not in profiles:
            raise HTTPException(status_code=404, detail=f"Category '{req.category}' not found.")
            
        ptype = "physical" if req.category in PHYSICAL_CATEGORIES else "app"
        user_specs = {
            "price": req.price,
            "description": req.description.strip()
        }
        
        coach_result = coach_spec(
            user_specs=user_specs,
            category=req.category,
            profile=profiles[req.category],
            product_type=ptype,
            use_mock=req.mock
        )
        return coach_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount compiled static React files if build directory exists
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend/dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    
    @app.exception_handler(404)
    async def custom_404_handler(request, __):
        # Fallback to index.html for SPA client-side routing
        return FileResponse(FRONTEND_DIR / "index.html")

if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
