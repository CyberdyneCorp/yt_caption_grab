import pytest
import json
from fastapi.testclient import TestClient
from src.main import app, extract_video_id

client = TestClient(app)

class TestAPI:
    """Test the FastAPI endpoints"""
    
    def test_root_endpoint(self):
        """Test the root endpoint returns correct response"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "YouTube Transcript API" in data["message"]
    
    def test_transcript_endpoint_invalid_url(self):
        """Test transcript endpoint with invalid URL"""
        response = client.get("/transcript?url=invalid_url")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid YouTube URL" in data["detail"]
    
    def test_transcript_endpoint_missing_url(self):
        """Test transcript endpoint without URL parameter"""
        response = client.get("/transcript")
        assert response.status_code == 422  # Validation error

class TestVideoIdExtraction:
    """Test video ID extraction from various YouTube URL formats"""
    
    def test_extract_video_id_standard_url(self):
        """Test extracting video ID from standard YouTube URL"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_short_url(self):
        """Test extracting video ID from short YouTube URL"""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_embed_url(self):
        """Test extracting video ID from embed YouTube URL"""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_v_url(self):
        """Test extracting video ID from /v/ YouTube URL"""
        url = "https://www.youtube.com/v/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_with_parameters(self):
        """Test extracting video ID from URL with additional parameters"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&list=PLtest"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_invalid_url(self):
        """Test extracting video ID from invalid URL raises ValueError"""
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            extract_video_id("https://example.com/not-youtube")
    
    def test_extract_video_id_empty_url(self):
        """Test extracting video ID from empty URL raises ValueError"""
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            extract_video_id("")

class TestNewEndpoints:
    """Test the new API endpoints added to the project"""
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data
        
        # Check values
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.0"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0
    
    def test_download_endpoint_invalid_url(self):
        """Test download endpoint with invalid URL"""
        response = client.get("/transcript/download?url=invalid_url&format=txt")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid YouTube URL" in data["detail"]
    
    def test_download_endpoint_missing_url(self):
        """Test download endpoint without URL parameter"""
        response = client.get("/transcript/download?format=txt")
        assert response.status_code == 422  # Validation error
    
    def test_download_endpoint_valid_format_parameter(self):
        """Test download endpoint accepts valid format parameters"""
        # Test with each valid format (will fail on video access, but format validation should pass)
        for format_type in ["txt", "srt", "vtt"]:
            response = client.get(f"/transcript/download?url=https://youtube.com/watch?v=dQw4w9WgXcQ&format={format_type}")
            # Should not be a 422 validation error (format is valid)
            assert response.status_code != 422
    
    def test_batch_endpoint_empty_request(self):
        """Test batch endpoint with empty URLs list"""
        response = client.post("/transcripts/batch", json={"urls": []})
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_requested"] == 0
        assert data["successful"] == 0
        assert data["failed"] == 0
        assert data["results"] == []
    
    def test_batch_endpoint_invalid_urls(self):
        """Test batch endpoint with invalid URLs"""
        batch_data = {
            "urls": ["invalid_url_1", "invalid_url_2"],
            "language": "en"
        }
        response = client.post("/transcripts/batch", json=batch_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_requested"] == 2
        assert data["successful"] == 0
        assert data["failed"] == 2
        assert len(data["results"]) == 2
        
        # Check that all results show failure
        for result in data["results"]:
            assert result["success"] is False
            assert "error" in result
            assert "Invalid YouTube URL" in result["error"]
    
    def test_batch_endpoint_mixed_urls(self):
        """Test batch endpoint with mix of valid and invalid URLs"""
        batch_data = {
            "urls": [
                "invalid_url",
                "https://youtube.com/watch?v=dQw4w9WgXcQ"  # Valid format but may fail on access
            ],
            "language": "en"
        }
        response = client.post("/transcripts/batch", json=batch_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_requested"] == 2
        assert len(data["results"]) == 2
        
        # First result should fail due to invalid URL
        assert data["results"][0]["success"] is False
        assert "Invalid YouTube URL" in data["results"][0]["error"]
        
        # Second result should at least have a valid video_id extracted
        assert data["results"][1]["video_id"] == "dQw4w9WgXcQ"
    
    def test_batch_endpoint_validation(self):
        """Test batch endpoint request validation"""
        # Missing urls field
        response = client.post("/transcripts/batch", json={"language": "en"})
        assert response.status_code == 422
        
        # Invalid JSON
        response = client.post("/transcripts/batch", json="invalid")
        assert response.status_code == 422