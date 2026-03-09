import os
import requests
from dotenv import load_dotenv
from backend.logger import setup_logger

load_dotenv()
logger = setup_logger("groq_service")

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1"

class GroqService:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

    def transcribe_audio(self, audio_path):
        """
        Transcribes audio using Whisper V3 via Groq with word-level timestamps.
        """
        url = f"{BASE_URL}/audio/transcriptions"
        
        files = {
            "file": (os.path.basename(audio_path), open(audio_path, "rb"), "audio/mpeg")
        }
        
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"]
        }

        try:
            logger.info(f"Transcribing audio {audio_path} via Groq...")
            response = requests.post(url, headers=self.headers, data=data, files=files)
            response.raise_for_status()
            result = response.json()
            logger.info("Transcription completed.")
            return result
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            if response := getattr(e, 'response', None):
                logger.error(f"Response: {response.text}")
            return None
        finally:
            files["file"][1].close()

    def convert_to_ass(self, transcription_result, output_ass_path, offset_seconds=0):
        """
        Converts Groq transcription result to .ASS Karaoke format.
        offset_seconds: Delay before subtitles start (e.g. for sync with intro).
        """
        words = transcription_result.get("words", [])
        if not words:
            logger.warning("No words found in transcription result.")
            return None

        # .ASS Header
        ass_content = [
            "[Script Info]",
            "Title: Generated Karaoke",
            "ScriptType: v4.00+",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # Style: Name, Font, Size, Primary (Active), Secondary (Wait), Outline, Back...
            "Style: Default,Arial,70,&H0000FFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,2,50,50,150,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        def format_time(seconds):
            # Apply offset
            t = max(0, seconds + offset_seconds)
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            cs = int((t % 1) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        # Group words into lines (e.g., 4 words per line)
        words_per_line = 4
        for i in range(0, len(words), words_per_line):
            line_words = words[i:i + words_per_line]
            start_time = format_time(line_words[0]["start"])
            end_time = format_time(line_words[-1]["end"])
            
            karaoke_text = ""
            for w in line_words:
                duration_cs = int((w["end"] - w["start"]) * 100)
                # Word-level karaoke timing
                karaoke_text += f"{{\\k{duration_cs}}}{w['word']} "
            
            ass_content.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{karaoke_text.strip()}")

        try:
            with open(output_ass_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ass_content))
            logger.info(f"Karaoke .ASS saved to {output_ass_path}")
            return output_ass_path
        except Exception as e:
            logger.error(f"Error saving .ASS: {e}")
            return None
