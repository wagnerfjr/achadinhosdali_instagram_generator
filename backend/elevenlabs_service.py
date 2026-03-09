import os
import requests
from dotenv import load_dotenv
from backend.logger import setup_logger

load_dotenv(override=True)
logger = setup_logger("elevenlabs_service")

class ElevenLabsService:
    def __init__(self):
        # Read API key dynamically to avoid stale values from top-level imports
        raw_key = os.getenv("ELEVENLABS_API_KEY")
        self.api_key = raw_key.strip() if raw_key else None
        
        if self.api_key:
            safe_key = f"{self.api_key[:4]}...{self.api_key[-4:]}"
            logger.info(f"ElevenLabsService initialized with key: {safe_key}")
        else:
            logger.warning("ElevenLabsService: No API KEY found in environment!")
        self.base_url = "https://api.elevenlabs.io/v1"

    def get_headers(self):
        key = (self.api_key or os.getenv("ELEVENLABS_API_KEY") or "").strip()
        return {
            "xi-api-key": key,
            "Content-Type": "application/json"
        }

    def clone_voice(self, name, audio_files):
        """
        Clones a voice using provided audio files.
        audio_files: list of local paths.
        """
        url = f"{self.base_url}/voices/add"
        headers = self.get_headers()
        # Multipart headers are handled by requests, but we need the API key
        if "Content-Type" in headers:
            del headers["Content-Type"]
        
        files = []
        for f in audio_files:
            files.append(("files", (os.path.basename(f), open(f, "rb"), "audio/mpeg")))

        data = {
            "name": name,
            "description": f"Clone of {name} for Content Factory"
        }

        try:
            logger.info(f"Cloning voice {name}...")
            response = requests.post(url, headers=headers, data=data, files=files)
            response.raise_for_status()
            voice_id = response.json().get("voice_id")
            logger.info(f"Voice cloned successfully. ID: {voice_id}")
            return voice_id
        except Exception as e:
            logger.error(f"Error cloning voice: {e}")
            if response := getattr(e, 'response', None):
                logger.error(f"Response: {response.text}")
            return None
        finally:
            for _, (_, f_obj, _) in files:
                f_obj.close()

    def generate_speech(self, text, output_path, voice_id=None):
        """
        Generates TTS audio for given text.
        If voice_id is None, it uses the one from .env (ELEVENLABS_VOICE_ID_LI).
        """
        v_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID_LI")
        if not v_id:
            logger.error("No Voice ID provided or found in .env (ELEVENLABS_VOICE_ID_LI)")
            return None
            
        url = f"{self.base_url}/text-to-speech/{v_id}"
        
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.85
            }
        }

        try:
            logger.info(f"Generating speech for text ({len(text)} chars) using voice {v_id}...")
            response = requests.post(url, json=payload, headers=self.get_headers())
            response.raise_for_status()
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"Audio saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            if response := getattr(e, 'response', None):
                logger.error(f"Response: {response.text}")
            return None
