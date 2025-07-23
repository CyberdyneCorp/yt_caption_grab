import pytest
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