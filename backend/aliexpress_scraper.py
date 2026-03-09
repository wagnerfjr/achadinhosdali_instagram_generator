import os
import re
import time
from .logger import setup_logger

logger = setup_logger("aliexpress_scraper")

def scrape_aliexpress_media(url: str):
    """
    Uses Stealth Playwright to extract video and image gallery from AliExpress.
    Returns: {"video_url": "", "images": []}
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    
    result = {"video_url": "", "images": []}
    logger.info(f"Stealth scraping AliExpress media for: {url}")
    
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
            
            # Go to product page
            page.goto(url, wait_until="load", timeout=90000)
            
            # Additional wait for lazy loading
            page.wait_for_timeout(5000)
            
            # Scroll a bit to trigger lazy loads
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_timeout(2000)
            
            html = page.content()
            
            # 1. Extract Video
            video_url = ""
            # Try video tags first
            video_elements = page.query_selector_all('video')
            for v in video_elements:
                src = v.get_attribute('src')
                # AliExpress often uses blob or complex src, but sometimes direct .mp4/m3u8
                if src and ('.mp4' in src or 'alicdn.com' in src):
                    video_url = src
                    break
            
            # Fallback to regex for common AliExpress video patterns
            if not video_url:
                # Common pattern: //video.aliexpress-media.com/... or alicdn.com
                mp4_matches = re.findall(r'https?:?//[^\s"\'<>]*?\.mp4', html)
                if mp4_matches:
                    video_url = mp4_matches[0]
                    if not video_url.startswith('http'): video_url = 'https:' + video_url
            
            result["video_url"] = video_url
            if video_url: logger.info(f"Found AliExpress Video: {video_url}")

            # 2. Extract Images (Gallery)
            img_urls = set()
            
            # AliExpress gallery selectors
            selectors = [
                '.item-detail-main-image img',
                '.magnifier-image img',
                '.slider--img--D7vO99t img', # New UI pattern
                'div[class*="gallery"] img'
            ]
            
            for selector in selectors:
                elements = page.query_selector_all(selector)
                for el in elements:
                    src = el.get_attribute('src')
                    if src and 'alicdn.com' in src:
                        # Clean suffix like _640x640.jpg to get original
                        clean_url = re.sub(r'_\d+x\d+.*?\.jpg$', '.jpg', src)
                        if not clean_url.startswith('http'): clean_url = 'https:' + clean_url
                        img_urls.add(clean_url)

            # Fallback regex for alicdn images
            if len(img_urls) < 3:
                raw_imgs = re.findall(r'https?:?//ae01\.alicdn\.com/kf/[^"\'\s<>]*?\.jpg', html)
                for img in raw_imgs:
                    clean_url = re.sub(r'_\d+x\d+.*?\.jpg$', '.jpg', img)
                    if not clean_url.startswith('http'): clean_url = 'https:' + clean_url
                    img_urls.add(clean_url)
            
            result["images"] = list(img_urls)[:10]
            logger.info(f"Found {len(result['images'])} images for AliExpress.")
            
            browser.close()
            return result
    except Exception as e:
        logger.error(f"AliExpress stealth scraping failed: {e}")
        return result
