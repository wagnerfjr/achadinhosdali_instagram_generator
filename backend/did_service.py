import os
import time
import requests
from dotenv import load_dotenv
from backend.logger import setup_logger

load_dotenv()
logger = setup_logger("did_service")

API_KEY = os.getenv("D_ID_API_KEY")
BASE_URL = "https://api.d-id.com"

class DIDService:
    def __init__(self):
        # API Key is usually Basic Auth or Bearer
        if not API_KEY.startswith("Basic") and not API_KEY.startswith("Bearer"):
            auth_header = f"Basic {API_KEY}"
        else:
            auth_header = API_KEY
            
        self.headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "accept": "application/json"
        }

    def upload_image(self, image_path):
        """Uploads a local image and returns its ID."""
        url = f"{BASE_URL}/images"
        files = {"image": (os.path.basename(image_path), open(image_path, "rb"), "image/png")}
        try:
            logger.info(f"Uploading image {image_path} to D-ID...")
            response = requests.post(url, headers={"Authorization": self.headers["Authorization"]}, files=files)
            response.raise_for_status()
            return response.json().get("url")
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response Body: {e.response.text}")
            return None
        finally:
            files["image"][1].close()

    def upload_audio(self, audio_path):
        """Uploads a local audio and returns its ID."""
        url = f"{BASE_URL}/audios"
        files = {"audio": (os.path.basename(audio_path), open(audio_path, "rb"), "audio/mpeg")}
        try:
            logger.info(f"Uploading audio {audio_path} to D-ID...")
            response = requests.post(url, headers={"Authorization": self.headers["Authorization"]}, files=files)
            response.raise_for_status()
            return response.json().get("url")
        except Exception as e:
            logger.error(f"Audio upload failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response Body: {e.response.text}")
            return None
        finally:
            files["audio"][1].close()

    def generate_talk(self, image_url, audio_url):
        """
        Starts a D-ID Talk generation using uploaded IDs.
        """
        url = f"{BASE_URL}/talks"
        
        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url
            },
            "config": {
                "fluent": "true",
                "pad_audio": "0.0",
                "driver_expressions": {
                    "expressions": [
                        {"expression": "happy", "start_frame": 0, "intensity": 1.0}
                    ]
                }
            }
        }

        try:
            logger.info("Requesting D-ID Talk generation...")
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            talk_id = response.json().get("id")
            logger.info(f"D-ID Talk started. ID: {talk_id}")
            return talk_id
        except Exception as e:
            logger.error(f"Error starting D-ID Talk: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def get_talk_status(self, talk_id):
        """Polls for the talk status."""
        url = f"{BASE_URL}/talks/{talk_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting talk status: {e}")
            return None

    def wait_for_talk(self, talk_id, timeout=120, poll_interval=5):
        """
        Sync wait for talk completion.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_obj = self.get_talk_status(talk_id)
            if not status_obj:
                break
                
            status = status_obj.get("status")
            logger.info(f"D-ID Status: {status}")
            
            if status == "done":
                return status_obj.get("result_url")
            elif status == "error":
                logger.error(f"D-ID Error: {status_obj.get('error')}")
                break
                
            time.sleep(poll_interval)
        
        logger.error("D-ID generation timed out.")
        return None
