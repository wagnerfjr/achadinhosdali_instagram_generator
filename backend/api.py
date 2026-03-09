import json
import os
import requests
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .product_loader import load_products, get_product
from .caption_generator import generate_caption, generate_seo_caption
from .shopee_service import ShopeeAffiliateClient
from .logger import setup_logger
from dotenv import load_dotenv
load_dotenv(override=True)
from .gdrive_service import GoogleDriveService
from .video_registry_service import register_video
from .instagram_service import post_reel, post_content
from backend.elevenlabs_service import ElevenLabsService
from backend.groq_service import GroqService
from backend.did_service import DIDService
from backend.video_engine_v4 import VideoEngineV4
from backend.video_templates import VideoTemplateFactory
from backend.utils.text_processor import format_currency_to_speech, format_numbers_to_speech, clean_product_name
from backend.utils.progress_tracker import update_progress, get_progress
from backend.utils.audio_utils import extract_audio_from_video
from backend.utils.script_generator import generate_viral_script
from .scraper import scrape_product_media

logger = setup_logger("api")
shopee_client = ShopeeAffiliateClient()
gdrive_service = GoogleDriveService()
elevenlabs_service = ElevenLabsService()
groq_service = GroqService()
did_service = DIDService()
video_engine = VideoEngineV4()
template_factory = VideoTemplateFactory(video_engine, groq_service, elevenlabs_service)

INTRO_PATH = "assets/intros/Olha_o_que_eu_encontrei_hoje.mp4"

# Instagram auto-post flag (set INSTAGRAM_AUTO_POST=true in .env to enable)
INSTAGRAM_AUTO_POST = os.getenv("INSTAGRAM_AUTO_POST", "false").lower() == "true"

app = FastAPI(title="Affiliate Video Generator MVP")

# Paths
OUTPUT_DIR = "output/videos"
APPROVED_DIR = "output/approved"

# Mount static files for frontend
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
# Mount root as a static file shortcut to index.html (we'll do this in main.py)

@app.get("/products")
def api_products(limit: int = 50):
    """Fetch raw products from VPS database."""
    products = load_products(limit)
    return {"status": "success", "data": products}

@app.post("/generate/{product_id}")
def api_generate(product_id: str):
    """Generates the hybrid video using VideoEngineV4 (Redirects to Content Factory logic)."""
    return api_generate_content_factory(product_id)

@app.post("/generate-influencer/{product_id}")
def api_generate_influencer(product_id: str):
    """Alias for the Li Avatar hybrid generation."""
    return api_generate_content_factory(product_id)

class RejectFeedback(BaseModel):
    feedback: str

@app.post("/reject/{product_id}")
def api_reject(product_id: str, payload: RejectFeedback):
    """Regenerates the caption based on feedback."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    try:
        # For this MVP, we only regenerate the caption to save time. 
        # Regenerating the video with full AI changes is a future extension.
        new_caption = generate_caption(product, feedback=payload.feedback)
        
        return {
            "status": "success",
            "message": "Content regenerated based on feedback",
            "caption": new_caption,
            "video_url": f"/api/video/{product_id}" # return same video url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ApprovePayload(BaseModel):
    caption: str

@app.post("/approve/{product_id}")
def api_approve(product_id: str, payload: ApprovePayload):
    """Saves the approved video and caption."""
    source_video = os.path.join(OUTPUT_DIR, f"{product_id}.mp4")
    # Check for Li version if standard is not found
    if not os.path.exists(source_video):
        source_video = os.path.join(OUTPUT_DIR, f"{product_id}_li.mp4")
    
    if not os.path.exists(source_video):
        raise HTTPException(status_code=404, detail=f"Generated video not found (Checked: {product_id}.mp4 and {product_id}_li.mp4)")
        
    if not os.path.exists(APPROVED_DIR):
        os.makedirs(APPROVED_DIR)
        
    dest_video = os.path.join(APPROVED_DIR, f"{product_id}.mp4")
    dest_caption = os.path.join(APPROVED_DIR, f"{product_id}.txt")
    
    try:
        # Keep original in output/videos, save a copy in approved/
        with open(source_video, "rb") as fsrc:
            with open(dest_video, "wb") as fdst:
                fdst.write(fsrc.read())
                
        with open(dest_caption, "w", encoding="utf-8") as f:
            f.write(payload.caption)
            
        # 3. Upload to Google Drive (if service is available)
        gdrive_error = None
        video_drive_id = None
        if gdrive_service.service:
            logger.info(f"Uploading files to Google Drive for product {product_id}...")
            video_drive_id = gdrive_service.upload_file(dest_video, 'video/mp4')
            c_id = gdrive_service.upload_file(dest_caption, 'text/plain')
            if not video_drive_id or not c_id:
                gdrive_error = "Sync failed (Check diag.log/quota)"

        # 4. Register video in Achadinhos external system
        registry_ok = False
        if video_drive_id:
            product = get_product(product_id)
            video_filename = os.path.basename(dest_video)
            tamanho_bytes = os.path.getsize(dest_video) if os.path.exists(dest_video) else None
            affiliate_link = (product or {}).get("affiliate_url") or (product or {}).get("shopee_url")

            registry_ok = register_video(
                product_id=product_id,
                google_drive_file_id=video_drive_id,
                nome_arquivo=product_id,
                affiliate_link=affiliate_link,
                platform_target="tiktok",
                resolucao="1080x1920",
                tamanho_bytes=tamanho_bytes,
                modelo_ia="conteudo-factory",
            )

        # 5. Auto-post to Instagram if flag is enabled
        instagram_result = None
        if INSTAGRAM_AUTO_POST:
            logger.info(f"INSTAGRAM_AUTO_POST=true — posting Reel for {product_id}...")
            ig_caption = payload.caption
            instagram_result = post_reel(
                product_id=product_id,
                local_video_path=dest_video,
                caption=ig_caption,
            )
            logger.info(f"Instagram result: {instagram_result}")

        ig_status = None
        if instagram_result:
            ig_status = "Published" if instagram_result["status"] == "success" else f"Failed: {instagram_result.get('error', '')}"

        return {
            "status": "success" if not gdrive_error else "warning",
            "message": "Content saved locally!",
            "gdrive_status": "Success" if (gdrive_service.service and not gdrive_error) else (gdrive_error or "Disabled"),
            "registry_status": "Registered" if registry_ok else ("Skipped" if not video_drive_id else "Failed"),
            "local_path": f"output/approved/{product_id}/",
            "instagram_status": ig_status,
            "instagram_auto_post": INSTAGRAM_AUTO_POST,
        }
    except Exception as e:
        logger.error(f"Approval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
def api_config():
    """Returns public runtime config for the frontend (e.g. feature flags)."""
    return {
        "instagram_auto_post": INSTAGRAM_AUTO_POST,
    }


class InstagramPostPayload(BaseModel):
    caption: str = ""
    format: str = "REELS" # or "STORIES"


@app.post("/instagram/post/{product_id}")
def api_instagram_post(product_id: str, payload: InstagramPostPayload):
    """Manually posts a saved video as an Instagram Reel or Story."""
    format_type = payload.format.upper()
    
    # Look for the approved video file
    video_path = os.path.join(APPROVED_DIR, f"{product_id}.mp4")
    if not os.path.exists(video_path):
        # Fallback to output/videos with format-specific suffix
        suffix = "_reel" if format_type == "REELS" else "_story"
        video_path = os.path.join(OUTPUT_DIR, f"{product_id}{suffix}.mp4")
    
    if not os.path.exists(video_path):
        # Last resort fallback
        video_path = os.path.join(OUTPUT_DIR, f"{product_id}_li.mp4")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Approved video not found. Save first.")

    product = get_product(product_id)
    extra = {}
    if format_type == "REELS" and product.get("image_url"):
        extra["cover_url"] = product["image_url"]

    result = post_content(
        product_id=product_id,
        media_paths=video_path,
        caption=payload.caption,
        media_type=format_type,
        **extra
    )

    if result["status"] == "success":
        return {"status": "success", "media_id": result["media_id"]}
    else:
        raise HTTPException(status_code=502, detail=result.get("error", "Instagram post failed"))


@app.get("/curated-products")
def api_curated_products(days: int = None, min_discount: int = None, force: bool = False):
    """
    Returns the 'Elite' products from the last X days.
    If force=False, returns the last cached curation if available.
    """
    cache_path = "temp/last_curation.json"
    
    # 1. Return cache if not forced
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                logger.info("Returning cached curation results.")
                return {"status": "success", "count": len(cached_data), "data": cached_data, "cached": True}
        except Exception as e:
            logger.warning(f"Failed to read curation cache: {e}")

    cur_days = days or int(os.getenv("VIDEO_CURATION_DAYS", 7))
    cur_min = min_discount or int(os.getenv("VIDEO_MIN_DISCOUNT", 30))
    
    # 1. Fetch from DB
    from .product_loader import load_products_by_date
    products = load_products_by_date(cur_days)
    
    curated = []
    total = len(products)
    logger.info(f"Curating {total} products from last {cur_days} days...")
    
    for i, p in enumerate(products):
        if i % 10 == 0:
            logger.info(f"Curation progress: {i}/{total} products analyzed...")
            
        try:
            # 2. Double-Check Live Price
            live_info = shopee_client.get_item_info(p['item_id'])
            if not live_info: continue
            
            p_orig = float(p.get('price_before_discount', p['price']))
            p_live = float(live_info.get('priceMin', p.get('price', p_orig)))
            p_discount = ((p_orig - p_live) / p_orig) * 100 if p_orig > 0 else 0
            
            # 3. AI Insights / Scoring
            status_tag = "Verificado agora"
            if p_discount < cur_min:
                # Scenario B: Expirado
                status_tag = "Oferta Expirada"
            elif p_discount >= p.get('discount_rate', 0) + 2 and float(live_info.get('ratingStar', 0)) >= 4.7:
                # Scenario C: Oportunidade Única
                status_tag = "Oportunidade Única"
            
            # Only show valid or unique ones
            if status_tag != "Oferta Expirada":
                p.update({
                    "current_price": p_live,
                    "current_discount": round(p_discount, 1),
                    "ai_status_tag": status_tag,
                    "shopee_url": live_info.get('offerLink', p.get('affiliate_url')),
                    "sales_count": live_info.get('sales', 0)
                })
                curated.append(p)
                
        except Exception as e:
            logger.warning(f"Error curating product {p['id']}: {e}")

    logger.info(f"Curation finished. Found {len(curated)} premium offers out of {total} analyzed.")
    
    # Save to cache
    try:
        if not os.path.exists("temp"): os.makedirs("temp")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(curated, f, ensure_ascii=False, indent=4)
            logger.info(f"Curation results saved to {cache_path}")
    except Exception as e:
        logger.error(f"Failed to save curation cache: {e}")

    return {"status": "success", "count": len(curated), "data": curated, "cached": False}

@app.post("/generate-reels/{product_id}")
def api_generate_reels(product_id: str):
    """Generates a Reels-formatted video (No intro, no price)."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        update_progress(product_id, "starting", 5, "Iniciando geração de REELS...")
        
        # 1. Media Discovery
        update_progress(product_id, "discovery", 10, "Buscando mídia original...")
        media = scrape_product_media(product['affiliate_url'], product.get('platform', 'Shopee'))
        if media.get("video_url"): product["video_url"] = media["video_url"]
        if media.get("images"): product["images"] = media["images"]

        # 2. Build Video via Factory
        video_path = template_factory.build_reels(product)
        
        # 3. Generate SEO Caption
        update_progress(product_id, "captioning", 95, "Gerando legenda SEO ultra-potente...")
        caption = generate_seo_caption(product, format_type="reels")
        
        return {
            "status": "success",
            "product_id": product_id,
            "video_url": f"/api/video/{product_id}_reel",
            "caption": caption,
            "type": "reels"
        }
    except Exception as e:
        logger.error(f"Generate Reels Error: {e}")
        update_progress(product_id, "error", 0, f"Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-stories/{product_id}")
def api_generate_stories(product_id: str):
    """Generates a Stories-formatted video (Full sandwich with price)."""
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        update_progress(product_id, "starting", 5, "Iniciando geração de STORIES...")
        
        # 1. Media Discovery
        update_progress(product_id, "discovery", 10, "Buscando mídia original...")
        media = scrape_product_media(product['affiliate_url'], product.get('platform', 'Shopee'))
        if media.get("video_url"): product["video_url"] = media["video_url"]
        if media.get("images"): product["images"] = media["images"]

        # 2. Build Video via Factory
        video_path = template_factory.build_stories(product)
        
        # 3. Stories typically don't have captions (stickers/text overlays are used instead)
        update_progress(product_id, "captioning", 95, "Finalizando Stories (Sem legenda)...")
        caption = ""
        
        return {
            "status": "success",
            "product_id": product_id,
            "video_url": f"/api/video/{product_id}_story",
            "caption": caption,
            "type": "stories"
        }
    except Exception as e:
        logger.error(f"Generate Stories Error: {e}")
        update_progress(product_id, "error", 0, f"Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve-reels/{product_id}")
def api_approve_reels(product_id: str, payload: ApprovePayload):
    """Approves and optionally auto-posts a Reels video."""
    return _approve_workflow(product_id, payload.caption, format_type="REELS")

@app.post("/approve-stories/{product_id}")
def api_approve_stories(product_id: str, payload: ApprovePayload):
    """Approves and optionally auto-posts a Stories video."""
    return _approve_workflow(product_id, payload.caption, format_type="STORIES")

def _approve_workflow(product_id: str, caption: str, format_type: str):
    """Shared internal workflow for approving and posting different formats."""
    suffix = "_reel" if format_type == "REELS" else "_story"
    source_video = os.path.join(OUTPUT_DIR, f"{product_id}{suffix}.mp4")
    
    if not os.path.exists(source_video):
        # Fallback to standard Li if template-specific not found
        source_video = os.path.join(OUTPUT_DIR, f"{product_id}_li.mp4")
        
    if not os.path.exists(source_video):
        raise HTTPException(status_code=404, detail="Video file not found")

    if not os.path.exists(APPROVED_DIR): os.makedirs(APPROVED_DIR)
    
    dest_video = os.path.join(APPROVED_DIR, f"{product_id}.mp4")
    dest_caption = os.path.join(APPROVED_DIR, f"{product_id}.txt")
    
    try:
        shutil.copy(source_video, dest_video)
        with open(dest_caption, "w", encoding="utf-8") as f:
            f.write(caption)
            
        # GDrive sync
        video_drive_id = None
        if gdrive_service.service:
            video_drive_id = gdrive_service.upload_file(dest_video, 'video/mp4')
            gdrive_service.upload_file(dest_caption, 'text/plain')

        # Registry
        registry_ok = False
        if video_drive_id:
            product = get_product(product_id)
            affiliate_link = (product or {}).get("affiliate_url") or (product or {}).get("shopee_url")
            
            registry_ok = register_video(
                product_id=product_id,
                google_drive_file_id=video_drive_id,
                nome_arquivo=product_id,
                affiliate_link=affiliate_link,
                platform_target=format_type.lower(),
                modelo_ia="template-factory"
            )

        # Auto-post logic
        ig_status = None
        if INSTAGRAM_AUTO_POST:
            product = get_product(product_id)
            extra = {}
            if format_type == "REELS" and product.get("image_url"):
                extra["cover_url"] = product["image_url"]
            
            res = post_content(product_id, dest_video, caption, media_type=format_type, **extra)
            ig_status = "Published" if res["status"] == "success" else f"Failed: {res.get('error')}"

        return {
            "status": "success",
            "instagram_status": ig_status,
            "instagram_auto_post": INSTAGRAM_AUTO_POST
        }
    except Exception as e:
        logger.error(f"Approve workflow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/progress/{product_id}")
def api_get_progress(product_id: str):
    """Returns the current generation progress."""
    return get_progress(product_id)

@app.get("/video/{product_id}")
def get_video(product_id: str):
    """Stream generated MP4 video."""
    video_path = os.path.join(OUTPUT_DIR, f"{product_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
        
    return FileResponse(video_path, media_type="video/mp4")

@app.get("/logs")
def api_logs(lines: int = 100):
    """Returns the last lines of the local diag.log file."""
    log_file = "diag.log"
    if not os.path.exists(log_file):
        return {"status": "error", "message": "Log file not found"}
        
    try:
        # Detect encoding or try UTF-8 with fallback
        # On Windows, PowerShell redirects often create UTF-16
        with open(log_file, "rb") as f:
            raw_data = f.read()
            
        # Try UTF-8 first
        try:
            content = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Try UTF-16 (common for PS redirects)
                content = raw_data.decode('utf-16')
            except UnicodeDecodeError:
                # Fallback to latin-1 or similar
                content = raw_data.decode('latin-1', errors='replace')
                
        all_lines = content.splitlines()
        last_lines = all_lines[-lines:]
        return {"status": "success", "logs": "\n".join(last_lines)}
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
