"""
Tests for API security features in the Credit Scoring service
"""
import pytest
import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'models', 'serving'))

# Ensure API_KEY is not set for tests
if 'API_KEY' in os.environ:
    del os.environ['API_KEY']

@pytest.fixture
def mock_model():
    """Mock LightGBM model"""
    model = Mock()
    model.predict_proba = Mock(return_value=np.array([[0.6, 0.4]]))
    model.feature_name_ = ['feature1', 'feature2', 'feature3']
    return model

@pytest.fixture
def mock_explainer():
    """Mock SHAP explainer"""
    explainer = Mock()
    explainer.shap_values = Mock(return_value=np.array([[0.1, 0.2, 0.3]]))
    return explainer

@pytest.fixture
def app_client(mock_model, mock_explainer, monkeypatch):
    """Create test client with mocked dependencies"""
    # Ensure API_KEY is not set
    monkeypatch.delenv('API_KEY', raising=False)
    monkeypatch.setenv('MODEL_PATH', '/tmp/model')
    
    # Mock mlflow loading
    with patch('mlflow.lightgbm.load_model', return_value=mock_model):
        with patch('shap.TreeExplainer', return_value=mock_explainer):
            # Import app after setting environment
            import app as app_module
            
            # Manually populate ml_models for testing
            app_module.ml_models['model'] = mock_model
            app_module.ml_models['explainer'] = mock_explainer
            app_module.expected_features = set()
            app_module.API_KEY = None  # Explicitly disable auth
            
            client = TestClient(app_module.app)
            yield client

class TestInputValidation:
    """Test input validation features"""
    
    def test_empty_features_rejected(self, app_client):
        """Empty features dictionary should be rejected"""
        response = app_client.post("/predict", json={"features": {}})
        assert response.status_code == 422
        
    def test_non_numeric_features_rejected(self, app_client):
        """Non-numeric feature values should be rejected"""
        response = app_client.post("/predict", json={
            "features": {"feature1": "not_a_number"}
        })
        assert response.status_code == 422
    
    def test_valid_features_accepted(self, app_client):
        """Valid numeric features should be accepted"""
        response = app_client.post("/predict", json={
            "features": {"feature1": 1.0, "feature2": 2.5, "feature3": -0.5}
        })
        assert response.status_code == 200
        assert "decision" in response.json()
        assert "risk_score" in response.json()
    
    def test_too_many_features_rejected(self, app_client):
        """More than MAX_FEATURES should be rejected"""
        # Create a dictionary with 301 features (over the limit)
        features = {f"feature_{i}": float(i) for i in range(301)}
        response = app_client.post("/predict", json={"features": features})
        assert response.status_code == 422

class TestErrorHandling:
    """Test error handling features"""
    
    def test_generic_error_message_on_internal_error(self, app_client, mock_model):
        """Internal errors should return generic message"""
        # Make the model raise an exception
        mock_model.predict_proba.side_effect = RuntimeError("Internal model error")
        
        response = app_client.post("/predict", json={
            "features": {"feature1": 1.0, "feature2": 2.0}
        })
        
        assert response.status_code == 500
        # Should not contain internal error details
        assert "Internal model error" not in response.json()["detail"]
        assert "error occurred processing your request" in response.json()["detail"].lower()

class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_endpoint_exists(self, app_client):
        """Health endpoint should be accessible"""
        response = app_client.get("/health")
        assert response.status_code == 200
    
    def test_health_endpoint_returns_status(self, app_client):
        """Health endpoint should return status information"""
        response = app_client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "model_loaded" in data
        assert "explainer_loaded" in data
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["explainer_loaded"] is True

class TestAuthentication:
    """Test API key authentication"""
    
    def test_prediction_without_auth_when_disabled(self, app_client):
        """When API_KEY is not set, authentication should be disabled"""
        response = app_client.post("/predict", json={
            "features": {"feature1": 1.0, "feature2": 2.0}
        })
        # Should succeed without API key
        assert response.status_code == 200
    
    def test_prediction_with_auth_enabled(self, mock_model, mock_explainer, monkeypatch):
        """When API_KEY is set, authentication should be required"""
        test_api_key = "test-secret-key"
        
        monkeypatch.setenv('API_KEY', test_api_key)
        monkeypatch.setenv('MODEL_PATH', '/tmp/model')
        
        with patch('mlflow.lightgbm.load_model', return_value=mock_model):
            with patch('shap.TreeExplainer', return_value=mock_explainer):
                # Need to reload app module to pick up new API_KEY
                import importlib
                import app as app_module
                importlib.reload(app_module)
                
                app_module.ml_models['model'] = mock_model
                app_module.ml_models['explainer'] = mock_explainer
                app_module.expected_features = set()
                
                client = TestClient(app_module.app)
                
                # Request without API key should fail
                response = client.post("/predict", json={
                    "features": {"feature1": 1.0}
                })
                assert response.status_code == 403
                
                # Request with correct API key should succeed
                response = client.post(
                    "/predict",
                    json={"features": {"feature1": 1.0}},
                    headers={"X-API-Key": test_api_key}
                )
                assert response.status_code == 200
                
                # Request with wrong API key should fail
                response = client.post(
                    "/predict",
                    json={"features": {"feature1": 1.0}},
                    headers={"X-API-Key": "wrong-key"}
                )
                assert response.status_code == 403

class TestResponseStructure:
    """Test response structure"""
    
    def test_prediction_response_structure(self, app_client):
        """Prediction response should have expected structure"""
        response = app_client.post("/predict", json={
            "features": {"feature1": 1.0, "feature2": 2.0, "feature3": 3.0}
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "decision" in data
        assert "risk_score" in data
        assert "top_risk_factors" in data
        
        # Check data types
        assert isinstance(data["decision"], str)
        assert data["decision"] in ["APPROVE", "REJECT"]
        assert isinstance(data["risk_score"], float)
        assert 0 <= data["risk_score"] <= 1
        assert isinstance(data["top_risk_factors"], list)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
