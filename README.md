# YouTube Transcript API (yt-dlp)

A FastAPI-based REST API that extracts transcripts from YouTube videos with multi-language support using yt-dlp.

## Features

- 🎥 Extract transcripts from any YouTube video
- 🌍 Multi-language support with automatic fallback
- 📝 Clean text formatting
- 🔍 List available languages for any video
- ⚡ Fast and reliable using yt-dlp for transcript extraction
- 🛡️ Comprehensive error handling
- 📖 Interactive API documentation

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Starting the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

The server will start on `http://localhost:8001`

#### Alternative ways to run:

```bash
# Run with auto-reload for development
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Run on default port 8000
uvicorn main:app --host 0.0.0.0 --port 8000

# Run only on localhost
uvicorn main:app --port 8001
```

### API Documentation

Once the server is running, visit:
- **Interactive docs**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### Endpoints

#### Get Transcript

```http
GET /transcript?url=<youtube_url>&lang=<language_code>
```

**Parameters:**
- `url` (required): YouTube video URL
- `lang` (optional): Language code (e.g., 'en', 'es', 'pt', 'fr'). Defaults to 'en'

**Example:**
```bash
curl "http://localhost:8001/transcript?url=https://youtube.com/watch?v=dQw4w9WgXcQ&lang=en"
```

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "transcript": "We're no strangers to love...",
  "available_languages": ["en", "es", "fr", "de"]
}
```

#### Get Available Languages

```http
GET /languages/{video_id}
```

**Example:**
```bash
curl "http://localhost:8001/languages/dQw4w9WgXcQ"
```

**Response:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "available_languages": [
    {
      "code": "en",
      "language": "English",
      "is_generated": false
    },
    {
      "code": "es",
      "language": "Spanish",
      "is_generated": true
    }
  ]
}
```

## Supported YouTube URL Formats

The API supports various YouTube URL formats:

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/embed/VIDEO_ID`
- `https://youtube.com/v/VIDEO_ID`

## Language Codes

Common language codes supported:

| Code | Language |
|------|----------|
| en   | English  |
| es   | Spanish  |
| fr   | French   |
| de   | German   |
| pt   | Portuguese |
| it   | Italian  |
| ja   | Japanese |
| ko   | Korean   |
| zh   | Chinese  |
| ru   | Russian  |

## Error Handling

The API provides clear error messages for common issues:

- **400 Bad Request**: Invalid YouTube URL format
- **404 Not Found**: Video not found or no transcript available
- **500 Internal Server Error**: Server-side issues

## Examples

### Python Example

```python
import requests

# Get transcript in English
response = requests.get(
    "http://localhost:8001/transcript",
    params={
        "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "lang": "en"
    }
)

data = response.json()
print(f"Transcript: {data['transcript']}")
```

### JavaScript Example

```javascript
const url = 'http://localhost:8001/transcript';
const params = new URLSearchParams({
    url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
    lang: 'en'
});

fetch(`${url}?${params}`)
    .then(response => response.json())
    .then(data => console.log(data.transcript));
```

### cURL Example

```bash
# Get Spanish transcript with fallback to English
curl -X GET "http://localhost:8001/transcript?url=https://youtube.com/watch?v=dQw4w9WgXcQ&lang=es"

# Check available languages first
curl -X GET "http://localhost:8001/languages/dQw4w9WgXcQ"
```

## Dependencies

- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI server for running the application
- **yt-dlp**: Python library for downloading YouTube videos and extracting transcripts
- **Pydantic**: Data validation and serialization

## Notes

- Not all YouTube videos have transcripts available
- Some videos only have auto-generated transcripts
- The API will attempt to fall back to English if the requested language is not available
- Uses yt-dlp for robust video information extraction and subtitle downloading
- Rate limiting may apply based on YouTube's policies

## License

This project is open source and available under the MIT License.