# Add this debug endpoint to main.py for deeper inspection

@app.get("/debug/{video_id}")
async def debug_video(video_id: str):
    """Debug endpoint to inspect video transcript availability and raw data"""
    try:
        logger.info(f"Debug request for video_id: {video_id}")
        
        # Get transcript list
        available_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        
        debug_info = {
            "video_id": video_id,
            "transcripts": [],
            "raw_transcript_objects": []
        }
        
        for transcript in available_transcripts:
            transcript_info = {
                "language_code": transcript.language_code,
                "language": transcript.language,
                "is_generated": transcript.is_generated,
                "translation_languages": list(transcript.translation_languages) if hasattr(transcript, 'translation_languages') else []
            }
            debug_info["transcripts"].append(transcript_info)
            
            # Try to get raw transcript object info
            try:
                raw_info = {
                    "language_code": transcript.language_code,
                    "video_id": transcript.video_id if hasattr(transcript, 'video_id') else video_id,
                    "object_type": str(type(transcript)),
                    "attributes": [attr for attr in dir(transcript) if not attr.startswith('_')]
                }
                debug_info["raw_transcript_objects"].append(raw_info)
            except Exception as e:
                debug_info["raw_transcript_objects"].append({
                    "language_code": transcript.language_code,
                    "error": str(e)
                })
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Debug endpoint failed for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")