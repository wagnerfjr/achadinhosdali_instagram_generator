import os
import re
import requests
from .logger import setup_logger
from .aliexpress_scraper import scrape_aliexpress_media

logger = setup_logger("scraper")

TEMP_DIR = "temp"

def scrape_product_media(url: str, platform: str = "Shopee"):
    """
    Dispatcher for scraping media based on product platform.
    """
    platform_clean = platform.lower() if platform else "shopee"
    
    if "aliexpress" in platform_clean:
        return scrape_aliexpress_media(url)
    
    return scrape_shopee_media(url)

def scrape_shopee_image(url: str, product_id: str) -> str:
    """
    Extracts Shop/Item IDs and hits the Shopee v4 API to get the fresh main image.
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    filepath = os.path.join(TEMP_DIR, f"{product_id}.jpg")
    
    # 1. Extract IDs from the affiliate URL
    clean_url = url.split('?')[0] if '?' in url else url
    match = re.search(r'/product/(\d+)/(\d+)', clean_url)
    if not match:
        logger.warning("Could not extract Shop/Item ID from the URL.")
        return None
        
    shop_id, item_id = match.groups()
    api_url = f"https://shopee.com.br/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": clean_url
    }
    
    try:
        logger.info(f"Hitting Shopee API: {api_url}")
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("data") and data["data"].get("image"):
                img_hash = data["data"]["image"]
                img_url = f"https://cf.shopee.com.br/file/{img_hash}"
                logger.info(f"Found image hash: {img_hash}. Downloading...")
                
                # Fetch fresh CDN image
                img_res = requests.get(img_url, stream=True, headers=headers)
                if img_res.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in img_res.iter_content(1024):
                            f.write(chunk)
                    return filepath
            logger.warning("Image hash not found in API response.")
        else:
            logger.error(f"API returned status {res.status_code}: {res.text[:200]}")
    except Exception as e:
        logger.error(f"API fetch failed: {e}")
        
    return None

def scrape_shopee_media(url: str):
    """
    Uses Stealth Playwright and regex to extract video and full image gallery
    bypassing Shopee's strict Bot Protection.
    Returns: {"video_url": "...", "images": ["...", ...]}
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    
    result = {"video_url": "", "images": []}
    logger.info(f"Stealth scraping media for: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            Stealth().use_sync(page)
            
            # Shopee links often redirect. Wait for the final product page.
            response = page.goto(url, wait_until="load", timeout=60000)
            
            # Wait for network to be idle to ensure SPA has finished rendering/navigating
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except:
                logger.warning("Timeout waiting for networkidle, proceeding anyway.")
            
            # Additional small wait for JS results
            page.wait_for_timeout(3000)
            
            html = page.content()
            
            # Extract media using specific selectors for better accuracy
            # 1. Look for Video MP4
            video_url = ""
            # Try to find video in the product gallery first
            video_elements = page.query_selector_all('video')
            for v in video_elements:
                src = v.get_attribute('src')
                if src and '.mp4' in src:
                    video_url = src
                    break
            
            # Fallback to regex if elements not found, but prioritize gallery area
            if not video_url:
                mp4_matches = set(re.findall(r'https://[^\s"\'<>]*?\.mp4', html))
                if mp4_matches:
                    # Filter for typical Shopee VOD links
                    vod_links = [l for l in mp4_matches if 'vod' in l or 'v.f.shopee' in l]
                    video_url = vod_links[0] if vod_links else list(mp4_matches)[0]
            
            result["video_url"] = video_url
            if video_url: logger.info(f"Found Video: {video_url}")

            # 2. Look for Product Images (Gallery only, ignore footer/cards)
            img_urls = []
            
            # Selector for main gallery images
            gallery_selectors = [
                'div[class*="product-gallery"] img',
                'div.product-briefing img',
                'div[class*="page-product"] img'
            ]
            
            found_urls = set()
            for selector in gallery_selectors:
                elements = page.query_selector_all(selector)
                for el in elements:
                    src = el.get_attribute('src')
                    if not src: continue
                    
                    # Clean URL and check if it matches Shopee CDN
                    if 'susercontent.com/file/' in src or 'cf.shopee.com.br/file/' in src:
                        # Remove suffixes like _tn or _zoom to get original resolution
                        clean_src = src.split('_')[0]
                        if clean_src not in found_urls:
                            # Heuristic: credit card icons are usually tiny or have specific patterns
                            # We can also check if the parent is the footer
                            is_footer = page.evaluate('''(el) => {
                                let p = el.parentElement;
                                while(p) {
                                    if(p.tagName === "FOOTER" || p.className.includes("footer")) return true;
                                    p = p.parentElement;
                                }
                                return false;
                            }''', el)
                            
                            if not is_footer:
                                found_urls.add(clean_src)
                                img_urls.append(clean_src)
            
            # Fallback to regex only if gallery search yields nothing
            if not img_urls:
                raw_matches = set(re.findall(r'https://[^\s"\'<>\\]*?\.susercontent\.com/file/[a-zA-Z0-9]{32}', html))
                raw_matches.update(re.findall(r'https://cf\.shopee\.com\.br/file/[a-zA-Z0-9]{32}', html))
                img_urls = list(raw_matches)

            if img_urls:
                result["images"] = img_urls[:10] # Cap at 10 high-quality images
                logger.info(f"Found {len(result['images'])} product images in gallery.")
                
            browser.close()
            return result
    except Exception as e:
        logger.error(f"Stealth scraping failed: {e}")
        return result
