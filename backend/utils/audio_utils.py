import os
import subprocess
import imageio_ffmpeg
from backend.logger import setup_logger

logger = setup_logger("audio_utils")

def extract_audio_from_video(video_path, output_audio_path):
    """
    Extracts audio track from a video file using FFmpeg binary directly.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # ffmpeg -i input.mp4 -q:a 0 -map a output.mp3
    cmd = [
        ffmpeg_exe,
        "-i", video_path,
        "-vn",          # No video
        "-acodec", "libmp3lame",
        "-q:a", "2",    # High quality
        "-y",           # Overwrite
        output_audio_path
    ]
    
    try:
        logger.info(f"Extracting audio from {video_path} using direct FFmpeg...")
        # Use stdout/stderr redirects to avoid deadlock on Windows
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            error_msg = result.stderr.decode()
            logger.error(f"FFmpeg extraction failed: {error_msg}")
            return None
            
        logger.info(f"Audio extraction successful: {output_audio_path}")
        return output_audio_path
    except Exception as e:
        logger.error(f"FFmpeg extraction failed: {str(e)}")
        return None

def get_audio_duration(audio_path):
    """Returns duration in seconds using ffprobe or pydub."""
    from pydub import AudioSegment
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
        return 0.0
