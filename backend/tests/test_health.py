"""
Health router property-based tests

**Feature: main-routes-refactor, Property 2: Health endpoint reflects service availability**
**Validates: Requirements 5.1, 5.2, 5.3**
"""
import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
from pathlib import Path

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.routers import health


@pytest.fixture(autouse=True)
def reset_availability():
    """Reset availability flags before each test"""
    health.set_availability(
        selenium=False,
        pdf=False,
        embedding=False,
        worker_pool=False
    )
    yield


@pytest.fixture
def app():
    """Create a fresh FastAPI app with health router for each test"""
    test_app = FastAPI()
    test_app.include_router(health.router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestHealthAvailability:
    """
    Property 2: Health endpoint reflects service availability
    
    For any combination of service availability flags (selenium, pdf, embedding, worker_pool),
    the GET / and GET /health endpoints SHALL return responses that accurately reflect
    the current availability state.
    """
    
    @settings(max_examples=100)
    @given(
        selenium=st.booleans(),
        pdf=st.booleans(),
        embedding=st.booleans(),
        worker_pool=st.booleans()
    )
    def test_root_endpoint_reflects_availability(
        self, client, selenium, pdf, embedding, worker_pool
    ):
        """
        Property test: GET / returns correct availability flags
        
        **Feature: main-routes-refactor, Property 2: Health endpoint reflects service availability**
        **Validates: Requirements 5.1**
        """
        # Set availability flags
        health.set_availability(
            selenium=selenium,
            pdf=pdf,
            embedding=embedding,
            worker_pool=worker_pool
        )
        
        # Call endpoint
        response = client.get("/")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Property: response must accurately reflect current availability state
        assert data["selenium_available"] == selenium
        assert data["pdf_extraction_available"] == pdf
        assert data["embedding_available"] == embedding
        assert data["upload_worker_pool_available"] == worker_pool
        assert data["status"] == "ok"
        assert data["message"] == "Gemini Chat Backend API"

    
    @settings(max_examples=100)
    @given(
        selenium=st.booleans(),
        pdf=st.booleans(),
        embedding=st.booleans(),
        worker_pool=st.booleans()
    )
    def test_health_endpoint_reflects_availability(
        self, client, selenium, pdf, embedding, worker_pool
    ):
        """
        Property test: GET /health returns correct availability flags
        
        **Feature: main-routes-refactor, Property 2: Health endpoint reflects service availability**
        **Validates: Requirements 5.2**
        """
        # Set availability flags
        health.set_availability(
            selenium=selenium,
            pdf=pdf,
            embedding=embedding,
            worker_pool=worker_pool
        )
        
        # Call endpoint
        response = client.get("/health")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Property: response must accurately reflect current availability state
        assert data["selenium"] == selenium
        assert data["pdf_extraction"] == pdf
        assert data["embedding"] == embedding
        assert data["upload_worker_pool"] == worker_pool
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"



class TestSetAvailability:
    """Test set_availability function correctly updates global flags"""
    
    @settings(max_examples=100)
    @given(
        selenium=st.booleans(),
        pdf=st.booleans(),
        embedding=st.booleans(),
        worker_pool=st.booleans()
    )
    def test_set_availability_updates_flags(
        self, selenium, pdf, embedding, worker_pool
    ):
        """
        Property test: set_availability correctly updates all flags
        
        **Feature: main-routes-refactor, Property 2: Health endpoint reflects service availability**
        **Validates: Requirements 5.3**
        """
        # Set availability
        health.set_availability(
            selenium=selenium,
            pdf=pdf,
            embedding=embedding,
            worker_pool=worker_pool
        )
        
        # Verify flags are updated
        assert health.SELENIUM_AVAILABLE == selenium
        assert health.PDF_EXTRACTION_AVAILABLE == pdf
        assert health.EMBEDDING_AVAILABLE == embedding
        assert health.WORKER_POOL_AVAILABLE == worker_pool
    
    def test_set_availability_default_worker_pool(self):
        """Test worker_pool defaults to False when not provided"""
        health.set_availability(selenium=True, pdf=True, embedding=True)
        
        assert health.SELENIUM_AVAILABLE is True
        assert health.PDF_EXTRACTION_AVAILABLE is True
        assert health.EMBEDDING_AVAILABLE is True
        assert health.WORKER_POOL_AVAILABLE is False
