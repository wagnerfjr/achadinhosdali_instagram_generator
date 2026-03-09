import os
import time
import requests
from .logger import setup_logger

logger = setup_logger("instagram_service")

# ----- Configuration -------------------------------------------------------
GRAPH_API_URL = "https://graph.facebook.com/v19.0"
TOKEN_DEBUG_URL = "https://graph.facebook.com/debug_token"
VPS_UPLOAD_URL = os.getenv("VPS_UPLOAD_URL", "https://liachadinhos.com.br/api/videos/upload-temp")
VPS_DELETE_URL = os.getenv("VPS_DELETE_URL", "https://liachadinhos.com.br/api/videos/delete-temp")

CONTAINER_POLL_ATTEMPTS = 10
CONTAINER_POLL_INTERVAL = 12  # seconds


# ----- Helpers ---------------------------------------------------------------

def _get_credentials() -> tuple[str, str]:
    """Returns (ig_user_id, access_token) from .env."""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    ig_user_id = os.getenv("ID_APLICATIVO", "").strip()
    token = os.getenv("INSTAGRAM_TOKEM", "").strip()
    
    if not ig_user_id or not token:
        raise RuntimeError("ID_APLICATIVO or INSTAGRAM_TOKEM not set in .env")
        
    logger.info(f"Using IG_ID: {ig_user_id[:4]}...{ig_user_id[-4:]} (len={len(ig_user_id)})")
    logger.info(f"Using Token: {token[:4]}...{token[-4:]} (len={len(token)})")
    
    return ig_user_id, token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ----- Step 1: Upload temp file to VPS --------------------------------------

def upload_file_to_vps(local_path: str) -> str:
    """
    Uploads a local file (MP4 or JPEG/PNG) to the VPS temporary endpoint.
    Returns the public URL of the uploaded file.
    Raises on failure.
    """
    war_token = os.getenv("MELI_SECRET")
    if not war_token:
        raise RuntimeError("MELI_SECRET (war-token) not set in .env")

    filename = os.path.basename(local_path)
    extension = filename.lower().split(".")[-1]
    
    # Determine MIME type
    if extension in ["mp4", "mov"]:
        mime_type = "video/mp4"
    elif extension in ["jpg", "jpeg"]:
        mime_type = "image/jpeg"
    elif extension in ["png"]:
        mime_type = "image/png"
    else:
        mime_type = "application/octet-stream"

    logger.info(f"Uploading {extension} to VPS temp storage: {filename} (MIME: {mime_type})")

    with open(local_path, "rb") as f:
        resp = requests.post(
            VPS_UPLOAD_URL,
            files={"file": (filename, f, mime_type)},
            headers={"x-war-token": war_token},
            timeout=180,  # Increased timeout for potentially larger files
        )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"VPS upload failed (HTTP {resp.status_code}): {resp.text[:300]}"
        )

    data = resp.json()
    public_url = data.get("url")
    if not public_url:
        raise RuntimeError(f"VPS upload response missing 'url': {data}")

    logger.info(f"File available at: {public_url}")
    return public_url


def upload_video_to_vps(local_path: str) -> str:
    """Deprecated: use upload_file_to_vps instead."""
    return upload_file_to_vps(local_path)


# ----- Step 2: Create Media Container on Meta ------------------------------

def create_media_container(
    ig_user_id: str, 
    token: str, 
    media_url: str, 
    caption: str = "", 
    media_type: str = "IMAGE",
    is_carousel_item: bool = False,
    extra_params: dict = None
) -> str:
    """
    Creates a media container on Meta Graph API.
    Supports REELS, IMAGE, VIDEO, STORIES.
    If is_carousel_item=True, it creates an item for a Carousel.
    """
    logger.info(f"Creating Instagram {media_type} media container...")
    headers = _auth_header(token)
    
    data = {
        "caption": caption,
    }
    
    if media_type == "REELS":
        data["media_type"] = "REELS"
        data["video_url"] = media_url
        data["share_to_feed"] = "true"
    elif media_type == "STORIES":
        # Meta expects 'image_url' or 'video_url' depending on content
        is_video = any(ext in media_url.lower() for ext in [".mp4", ".mov"])
        if is_video:
            data["media_type"] = "STORIES"
            data["video_url"] = media_url
        else:
            data["media_type"] = "STORIES"
            data["image_url"] = media_url
    elif media_type == "VIDEO":
        data["media_type"] = "VIDEO"
        data["video_url"] = media_url
    elif media_type == "IMAGE":
        # Note: If media_type is omitted, it defaults to IMAGE if image_url is present
        data["image_url"] = media_url
    elif media_type == "CAROUSEL":
        # This is for the parent container
        data["media_type"] = "CAROUSEL"
        # children param should be in extra_params as a comma-separated string of IDs
    
    if is_carousel_item:
        data["is_carousel_item"] = "true"
        # Containers for carousels shouldn't have captions (they go in the parent)
        data.pop("caption", None)

    if extra_params:
        data.update(extra_params)

    # Clean up empty values
    data = {k: v for k, v in data.items() if v is not None}

    resp = requests.post(
        f"{GRAPH_API_URL}/{ig_user_id}/media",
        headers=headers,
        data=data,
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Container creation failed (HTTP {resp.status_code}, {media_type}): {resp.text[:300]}"
        )

    container_id = resp.json().get("id")
    if not container_id:
        raise RuntimeError(f"Container creation response missing 'id': {resp.json()}")

    logger.info(f"Container created ({media_type}): {container_id}")
    return container_id


# ----- Step 3: Poll container status ---------------------------------------

def wait_container_ready(container_id: str, token: str) -> None:
    """
    Polls the container status until FINISHED or raises on ERROR/timeout.
    """
    logger.info(f"Polling container status for {container_id}...")
    headers = _auth_header(token)
    for attempt in range(1, CONTAINER_POLL_ATTEMPTS + 1):
        resp = requests.get(
            f"{GRAPH_API_URL}/{container_id}",
            params={"fields": "status_code"},
            headers=headers,
            timeout=15,
        )
        status = resp.json().get("status_code", "UNKNOWN")
        logger.info(f"  Attempt {attempt}/{CONTAINER_POLL_ATTEMPTS}: status={status}")

        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram container processing ERROR for {container_id}")
        if status in ("IN_PROGRESS", "PUBLISHED"):
            time.sleep(CONTAINER_POLL_INTERVAL)
        else:
            time.sleep(CONTAINER_POLL_INTERVAL)

    raise RuntimeError(
        f"Container {container_id} not ready after {CONTAINER_POLL_ATTEMPTS} attempts"
    )


# ----- Step 4: Publish the container ----------------------------------------

def publish_container(ig_user_id: str, token: str, container_id: str) -> str:
    """
    Publishes the media container as a Reel.
    Returns the published media ID.
    """
    logger.info(f"Publishing container {container_id}...")
    headers = _auth_header(token)
    resp = requests.post(
        f"{GRAPH_API_URL}/{ig_user_id}/media_publish",
        headers=headers,
        data={
            "creation_id": container_id,
        },
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Publish failed (HTTP {resp.status_code}): {resp.text[:300]}"
        )

    media_id = resp.json().get("id")
    logger.info(f"Reel published successfully! media_id={media_id}")
    return media_id


# ----- Step 5: Cleanup temp file on VPS ------------------------------------

def cleanup_temp_video(public_url: str) -> None:
    """
    Sends a DELETE request to the VPS to remove the temporary video file.
    Non-blocking — logs errors but does not raise.
    """
    war_token = os.getenv("MELI_SECRET", "")
    try:
        filename = public_url.rstrip("/").split("/")[-1]
        resp = requests.delete(
            VPS_DELETE_URL,
            json={"filename": filename},
            headers={"x-war-token": war_token},
            timeout=15,
        )
        if resp.status_code in (200, 204):
            logger.info(f"Temp file removed from VPS: {filename}")
        else:
            logger.warning(f"VPS cleanup returned HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Failed to cleanup VPS temp file: {e}")


# ----- Main Orchestrator ----------------------------------------------------

# ----- Main Orchestrators ---------------------------------------------------

def post_content(
    product_id: str, 
    media_paths: list[str] | str, 
    caption: str = "", 
    media_type: str = "REELS",
    **extra_params
) -> dict:
    """
    Unified orchestrator for Instagram publishing.
    Supports: REELS, IMAGE, VIDEO, STORIES, CAROUSEL.
    
    :param product_id: Internal ID for tracking
    :param media_paths: Path (str) or list of paths (list[str]) to local media files
    :param caption: Text for the post (ignored for STORIES)
    :param media_type: One of "REELS", "IMAGE", "VIDEO", "STORIES", "CAROUSEL"
    :return: dict with status and details
    """
    ig_user_id, token = _get_credentials()
    uploaded_urls = []
    
    try:
        # Normalize media_paths to list
        if isinstance(media_paths, str):
            media_paths = [media_paths]

        # 1. Upload all files to VPS
        for path in media_paths:
            public_url = upload_file_to_vps(path)
            uploaded_urls.append(public_url)

        # 2. Handle Container Creation
        container_id = None
        
        if media_type == "CAROUSEL":
            if len(uploaded_urls) < 2:
                raise ValueError("CAROUSEL requires at least 2 media items.")
            
            child_ids = []
            for url in uploaded_urls:
                # Carousel items can be IMAGE or VIDEO, Meta detects based on URL usually
                # or we can be explicit. For now, let's use IMAGE/VIDEO detection logic
                item_type = "VIDEO" if any(v in url.lower() for v in [".mp4", ".mov"]) else "IMAGE"
                child_id = create_media_container(
                    ig_user_id, token, url, "", item_type, is_carousel_item=True
                )
                child_ids.append(child_id)
            
            # Wait for all children to be ready (Meta requirement)
            logger.info(f"Waiting for {len(child_ids)} carousel children to be ready...")
            for cid in child_ids:
                wait_container_ready(cid, token)
            
            # Create the parent carousel container
            children_str = ",".join(child_ids)
            container_id = create_media_container(
                ig_user_id, token, "", caption, "CAROUSEL", extra_params={"children": children_str}
            )
        else:
            # Single media types (REELS, IMAGE, VIDEO, STORIES)
            container_id = create_media_container(
                ig_user_id, token, uploaded_urls[0], caption, media_type, extra_params=extra_params
            )

        # 3. Wait for main container processing
        wait_container_ready(container_id, token)

        # 4. Small extra wait (Meta recommended)
        logger.info("Container ready. Waiting 5-10s before publishing...")
        time.sleep(10 if media_type in ["REELS", "VIDEO"] else 5)

        # 5. Publish with Retry
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                logger.info(f"Publishing container {container_id} (Attempt {attempt + 1})...")
                media_id = publish_container(ig_user_id, token, container_id)
                
                return {
                    "status": "success",
                    "media_id": media_id,
                    "product_id": product_id,
                    "type": media_type
                }
            except Exception as e:
                last_error = str(e)
                if "code\": 1" in last_error or "500" in last_error:
                    logger.warning(f"Publish attempt {attempt + 1} failed with transient error. Retrying in 15s...")
                    time.sleep(15)
                else:
                    raise e
        
        raise Exception(f"Publish failed after {max_retries} attempts. Last error: {last_error}")

    except Exception as e:
        logger.error(f"post_content failed for product_id={product_id}, type={media_type}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "product_id": product_id,
        }

    finally:
        # Always attempt cleanup
        for url in uploaded_urls:
            cleanup_temp_video(url)


def post_reel(product_id: str, local_video_path: str, caption: str = "") -> dict:
    """
    Backward compatibility wrapper for post_reel.
    """
    return post_content(product_id, local_video_path, caption, media_type="REELS")
