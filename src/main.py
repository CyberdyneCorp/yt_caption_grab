from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
import yt_dlp
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging
import tempfile
import os
import time
import datetime
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global startup time for health endpoint
startup_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global startup_time
    startup_time = time.time()
    logger.info("🚀 YouTube Transcript API starting up...")
    logger.info("✅ Logging configured successfully")
    yield
    # Shutdown
    logger.info("👋 YouTube Transcript API shutting down...")

app = FastAPI(
    title="YouTube Transcript API (yt-dlp)", 
    version="2.0.0",
    lifespan=lifespan
)

class TranscriptResponse(BaseModel):
    video_id: str
    language: str
    transcript: str
    available_languages: List[str]

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    timestamp: str

class DownloadFormat(str, Enum):
    TXT = "txt"
    SRT = "srt" 
    VTT = "vtt"

class BatchRequest(BaseModel):
    urls: List[str]
    language: Optional[str] = "en"
    
class BatchVideoResult(BaseModel):
    url: str
    video_id: Optional[str] = None
    success: bool
    transcript: Optional[str] = None
    language: Optional[str] = None
    available_languages: Optional[List[str]] = None
    error: Optional[str] = None

class BatchResponse(BaseModel):
    total_requested: int
    successful: int
    failed: int
    results: List[BatchVideoResult]

def extract_video_id(url: str) -> str:
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
        r'youtube\.com\/embed\/([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError("Invalid YouTube URL")

def retry_yt_dlp_operation(operation_func, max_retries=3, delay=1):
    """Retry yt-dlp operations with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return operation_func()
        except (BrokenPipeError, ConnectionError, yt_dlp.DownloadError) as e:
            if attempt == max_retries - 1:
                raise e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        except Exception as e:
            # For other exceptions, don't retry
            raise e

def get_video_info(video_id: str) -> Dict[str, Any]:
    """Get video information including available subtitles"""
    print(f"🔧 Getting video info for: {video_id}")
    logger.info(f"Getting video info for: {video_id}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'listsubtitles': True,
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
        'http_chunk_size': 10485760,  # 10MB chunks
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls']  # Skip potentially problematic formats
            }
        }
    }
    
    def extract_info():
        print(f"⚙️  Starting yt-dlp extract_info for: {video_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url = f"https://www.youtube.com/watch?v={video_id}"
            print(f"🌐 Calling yt-dlp.extract_info for URL: {url}")
            result = ydl.extract_info(url, download=False)
            print(f"✅ Successfully extracted info for: {video_id}")
            return result
    
    try:
        return retry_yt_dlp_operation(extract_info)
    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp download error for {video_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Video not accessible: {str(e)}")
    except (BrokenPipeError, ConnectionError) as e:
        logger.error(f"Network error for {video_id}: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Network error, please try again: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to extract video info for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def download_subtitles(video_id: str, language: str = None) -> tuple[str, str]:
    """Download subtitles for a video"""
    logger.info(f"Downloading subtitles for {video_id}, language: {language}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'skip_download': True,
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls']  # Skip potentially problematic formats
                }
            }
        }
        
        if language:
            ydl_opts['subtitleslangs'] = [language]
        
        def download_operation():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                url = f"https://www.youtube.com/watch?v={video_id}"
                ydl.download([url])
                
                # Find downloaded subtitle files
                subtitle_files = []
                for file in os.listdir(temp_dir):
                    if file.startswith(video_id) and file.endswith('.vtt'):
                        subtitle_files.append(file)
                
                if not subtitle_files:
                    raise HTTPException(status_code=404, detail="No subtitles found for this video")
                
                # Use the first available subtitle file
                subtitle_file = subtitle_files[0]
                subtitle_path = os.path.join(temp_dir, subtitle_file)
                
                # Extract language from filename
                lang_match = re.search(rf'{video_id}\.([^.]+)\.vtt', subtitle_file)
                actual_language = lang_match.group(1) if lang_match else language or 'unknown'
                
                # Read and parse VTT content
                with open(subtitle_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                return content, actual_language
        
        try:
            return retry_yt_dlp_operation(download_operation)
        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp subtitle download error for {video_id}: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Failed to download subtitles: {str(e)}")
        except (BrokenPipeError, ConnectionError) as e:
            logger.error(f"Network error downloading subtitles for {video_id}: {str(e)}")
            raise HTTPException(status_code=503, detail=f"Network error, please try again: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to download subtitles for {video_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def parse_vtt_content(vtt_content: str) -> str:
    """Parse VTT content and extract clean text"""
    lines = vtt_content.split('\n')
    transcript_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip VTT header and metadata
        if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            i += 1
            continue
        
        # Check if line contains timestamp
        if '-->' in line:
            i += 1
            # Next lines contain the actual subtitle text
            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                text = lines[i].strip()
                # Remove HTML tags and clean up
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'&amp;', '&', text)
                text = re.sub(r'&lt;', '<', text)
                text = re.sub(r'&gt;', '>', text)
                if text:
                    transcript_lines.append(text)
                i += 1
        else:
            i += 1
    
    return ' '.join(transcript_lines)

def convert_to_srt(vtt_content: str) -> str:
    """Convert VTT content to SRT format"""
    lines = vtt_content.split('\n')
    srt_lines = []
    subtitle_count = 1
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip VTT header and metadata
        if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            i += 1
            continue
        
        # Check if line contains timestamp
        if '-->' in line:
            # Convert WebVTT timestamp to SRT format
            timestamp_line = line.replace('.', ',')  # SRT uses comma instead of dot
            srt_lines.append(str(subtitle_count))
            srt_lines.append(timestamp_line)
            
            i += 1
            # Collect subtitle text
            subtitle_text = []
            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                text = lines[i].strip()
                # Remove HTML tags and clean up
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'&amp;', '&', text)
                text = re.sub(r'&lt;', '<', text)
                text = re.sub(r'&gt;', '>', text)
                if text:
                    subtitle_text.append(text)
                i += 1
            
            if subtitle_text:
                srt_lines.extend(subtitle_text)
                srt_lines.append('')  # Empty line between subtitles
                subtitle_count += 1
        else:
            i += 1
    
    return '\n'.join(srt_lines)

def get_clean_vtt(vtt_content: str) -> str:
    """Return clean VTT content with proper headers"""
    if not vtt_content.startswith('WEBVTT'):
        return 'WEBVTT\n\n' + vtt_content
    return vtt_content

@app.get("/")
async def root():
    logger.info("🏠 Root endpoint accessed")
    print("🏠 Root endpoint accessed")  # Fallback print for debugging
    return {"message": "YouTube Transcript API (yt-dlp)", "usage": "GET /transcript?url=<youtube_url>&lang=<language_code>"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring and load balancers"""
    current_time = time.time()
    uptime = current_time - startup_time
    
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        uptime_seconds=round(uptime, 2),
        timestamp=datetime.datetime.now().isoformat()
    )

@app.get("/transcript/download")
async def download_transcript(
    url: str = Query(..., description="YouTube video URL"),
    format: DownloadFormat = Query(DownloadFormat.TXT, description="Download format: txt, srt, or vtt"),
    lang: Optional[str] = Query("en", description="Language code (e.g., 'en', 'es', 'pt')")
):
    """Download transcript in specified format (txt, srt, vtt)"""
    try:
        print(f"📥 Download request: url={url}, format={format}, lang={lang}")
        logger.info(f"📥 Download request: url={url}, format={format}, lang={lang}")
        
        video_id = extract_video_id(url)
        
        # Get video info first
        try:
            info = get_video_info(video_id)
        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Video not found or unavailable: {str(e)}")
        
        # Get available subtitle languages
        available_languages = []
        subtitles = info.get('subtitles', {})
        automatic_captions = info.get('automatic_captions', {})
        
        for lang_code in subtitles.keys():
            available_languages.append(lang_code)
        for lang_code in automatic_captions.keys():
            if lang_code not in available_languages:
                available_languages.append(lang_code)
        
        if not available_languages:
            raise HTTPException(status_code=404, detail="No subtitles available for this video")
        
        # Determine which language to use
        selected_language = None
        if lang in available_languages:
            selected_language = lang
        elif 'en' in available_languages:
            selected_language = 'en'
        else:
            selected_language = available_languages[0]
        
        # Download subtitles
        try:
            vtt_content, actual_language = download_subtitles(video_id, selected_language)
            
            # Convert to requested format
            if format == DownloadFormat.TXT:
                content = parse_vtt_content(vtt_content)
                media_type = "text/plain"
                filename = f"{video_id}_{actual_language}.txt"
            elif format == DownloadFormat.SRT:
                content = convert_to_srt(vtt_content)
                media_type = "text/srt"
                filename = f"{video_id}_{actual_language}.srt"
            elif format == DownloadFormat.VTT:
                content = get_clean_vtt(vtt_content)
                media_type = "text/vtt"
                filename = f"{video_id}_{actual_language}.vtt"
            
            logger.info(f"✅ Download successful for {video_id} ({actual_language}) in {format} format")
            
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except Exception as e:
            logger.error(f"Failed to download/convert subtitles for {video_id}: {str(e)}")
            raise HTTPException(status_code=503, detail=f"Unable to process transcript: {str(e)}")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in download for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing download: {str(e)}")

@app.get("/transcript", response_model=TranscriptResponse)
async def get_transcript(
    url: str = Query(..., description="YouTube video URL"),
    lang: Optional[str] = Query("en", description="Language code (e.g., 'en', 'es', 'pt')")
):
    try:
        print(f"📺 Transcript request received: url={url}, lang={lang}")
        logger.info(f"📺 Transcript request received: url={url}, lang={lang}")
        
        video_id = extract_video_id(url)
        print(f"🔍 Extracted video_id: {video_id}")
        logger.info(f"Processing transcript request for video_id: {video_id}, requested_lang: {lang}")
        
        # Get video info to check available subtitles
        try:
            info = get_video_info(video_id)
            logger.info(f"Successfully extracted video info for {video_id}")
        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {str(e)}")
            raise HTTPException(status_code=404, detail=f"Video not found or unavailable: {str(e)}")
        
        # Get available subtitle languages
        available_languages = []
        subtitles = info.get('subtitles', {})
        automatic_captions = info.get('automatic_captions', {})
        
        # Add manual subtitles
        for lang_code in subtitles.keys():
            available_languages.append(lang_code)
            logger.info(f"Found manual subtitle: {lang_code}")
        
        # Add automatic captions
        for lang_code in automatic_captions.keys():
            if lang_code not in available_languages:
                available_languages.append(lang_code)
            logger.info(f"Found automatic caption: {lang_code}")
        
        logger.info(f"Available languages for {video_id}: {available_languages}")
        
        if not available_languages:
            raise HTTPException(status_code=404, detail="No subtitles available for this video")
        
        # Determine which language to use
        selected_language = None
        if lang in available_languages:
            selected_language = lang
            logger.info(f"Using requested language: {lang}")
        elif 'en' in available_languages:
            selected_language = 'en'
            logger.info(f"Requested language '{lang}' not available, falling back to English")
        else:
            selected_language = available_languages[0]
            logger.info(f"Neither '{lang}' nor English available, using: {selected_language}")
        
        # Download and parse subtitles
        try:
            vtt_content, actual_language = download_subtitles(video_id, selected_language)
            transcript_text = parse_vtt_content(vtt_content)
            logger.info(f"Successfully extracted transcript for {video_id} ({actual_language}), length: {len(transcript_text)} chars")
            
            return TranscriptResponse(
                video_id=video_id,
                language=actual_language,
                transcript=transcript_text,
                available_languages=available_languages
            )
            
        except Exception as e:
            logger.error(f"Failed to download/parse subtitles for {video_id}: {str(e)}")
            raise HTTPException(status_code=503, detail=f"Unable to fetch transcript: {str(e)}")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching transcript: {str(e)}")

@app.get("/languages/{video_id}")
async def get_available_languages(video_id: str):
    try:
        info = get_video_info(video_id)
        
        languages = []
        subtitles = info.get('subtitles', {})
        automatic_captions = info.get('automatic_captions', {})
        
        # Add manual subtitles
        for lang_code, subtitle_list in subtitles.items():
            languages.append({
                "code": lang_code,
                "language": lang_code,
                "is_generated": False
            })
        
        # Add automatic captions
        for lang_code, caption_list in automatic_captions.items():
            if not any(l["code"] == lang_code for l in languages):
                languages.append({
                    "code": lang_code,
                    "language": lang_code,
                    "is_generated": True
                })
        
        return {"video_id": video_id, "available_languages": languages}
        
    except Exception as e:
        logger.error(f"Failed to get languages for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching available languages: {str(e)}")

@app.post("/transcripts/batch", response_model=BatchResponse)
async def batch_transcripts(request: BatchRequest):
    """Process multiple YouTube videos and return their transcripts"""
    print(f"📦 Batch request for {len(request.urls)} videos, lang={request.language}")
    logger.info(f"📦 Batch processing {len(request.urls)} videos, language: {request.language}")
    
    results = []
    successful = 0
    failed = 0
    
    for url in request.urls:
        result = BatchVideoResult(url=url, success=False)
        
        try:
            # Extract video ID
            video_id = extract_video_id(url)
            result.video_id = video_id
            logger.info(f"🔄 Processing video {video_id} in batch")
            
            # Get video info
            try:
                info = get_video_info(video_id)
            except Exception as e:
                result.error = f"Video not found or unavailable: {str(e)}"
                failed += 1
                results.append(result)
                continue
            
            # Get available languages
            available_languages = []
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            for lang_code in subtitles.keys():
                available_languages.append(lang_code)
            for lang_code in automatic_captions.keys():
                if lang_code not in available_languages:
                    available_languages.append(lang_code)
            
            result.available_languages = available_languages
            
            if not available_languages:
                result.error = "No subtitles available for this video"
                failed += 1
                results.append(result)
                continue
            
            # Determine language to use
            selected_language = None
            if request.language in available_languages:
                selected_language = request.language
            elif 'en' in available_languages:
                selected_language = 'en'
            else:
                selected_language = available_languages[0]
            
            # Download and parse transcript
            try:
                vtt_content, actual_language = download_subtitles(video_id, selected_language)
                transcript_text = parse_vtt_content(vtt_content)
                
                result.success = True
                result.transcript = transcript_text
                result.language = actual_language
                successful += 1
                
                logger.info(f"✅ Batch: Successfully processed {video_id} ({actual_language})")
                
            except Exception as e:
                result.error = f"Failed to download transcript: {str(e)}"
                failed += 1
                
        except ValueError as e:
            result.error = f"Invalid YouTube URL: {str(e)}"
            failed += 1
        except Exception as e:
            result.error = f"Unexpected error: {str(e)}"
            failed += 1
            logger.error(f"❌ Batch: Unexpected error for {url}: {str(e)}")
        
        results.append(result)
    
    logger.info(f"📊 Batch complete: {successful} successful, {failed} failed out of {len(request.urls)}")
    
    return BatchResponse(
        total_requested=len(request.urls),
        successful=successful,
        failed=failed,
        results=results
    )

