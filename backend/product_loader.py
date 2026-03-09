import json
from .database import run_query
from .logger import setup_logger

logger = setup_logger("loader")

def load_products(limit: int = 50) -> list[dict]:
    """
    Loads raw products from the VPS database that were posted recently.
    Parses media URLs and removes unnecessary fields.
    """
    sql = f"""
        SELECT 
            rp.id, rp.platform, rp.external_id, rp.name, rp.price, rp.price_before_discount, 
            rp.affiliate_url, rp.raw_media_urls, rp.discount_rate, rp.sales, ci.status
        FROM raw_products rp
        INNER JOIN content_items ci
        ON rp.id = ci.product_id
        WHERE ci.status = 'Posted'
        ORDER BY rp.discovery_date DESC
        LIMIT {limit}
    """
    
    results = run_query(sql)
    clean_products = []
    
    for row in results:
        # Parse media from JSON string
        images = []
        video_url = ""
        try:
            if row.get("raw_media_urls"):
                media_data = json.loads(row["raw_media_urls"])
                image_url = media_data.get("image", "")
                images = media_data.get("images", [image_url] if image_url else [])
                video_url = media_data.get("videoUrl", "")
        except json.JSONDecodeError:
            pass
            
        clean_product = {
            "id": row.get("id"),
            "item_id": row.get("external_id") if row.get("platform") == "Shopee" else (row.get("external_id") or row.get("id")),
            "platform": row.get("platform"),
            "name": row.get("name"),
            "price": float(row.get("price") or 0.0),
            "price_before_discount": float(row.get("price_before_discount") or 0.0),
            "discount_rate": float(row.get("discount_rate") or 0.0),
            "affiliate_url": row.get("affiliate_url"),
            "image_url": image_url,
            "images": images,
            "video_url": video_url,
            "status": row.get("status")
        }
        clean_products.append(clean_product)
        
    return clean_products

def get_product(product_id: str) -> dict | None:
    """Gets a single product by ID."""
    sql = f"""
        SELECT 
            rp.id, rp.platform, rp.external_id, rp.name, rp.price, rp.price_before_discount, 
            rp.affiliate_url, rp.raw_media_urls, rp.discount_rate, rp.sales
        FROM raw_products rp
        WHERE rp.id = '{product_id}'
        LIMIT 1
    """
    results = run_query(sql)
    if not results:
        return None
        
    row = results[0]
    
    # Parse media from JSON string
    images = []
    video_url = ""
    try:
        if row.get("raw_media_urls"):
            media_data = json.loads(row["raw_media_urls"])
            image_url = media_data.get("image", "")
            images = media_data.get("images", [image_url] if image_url else [])
            video_url = media_data.get("videoUrl", "")
    except json.JSONDecodeError:
        pass
        
    return {
        "id": row.get("id"),
        "item_id": row.get("external_id") if row.get("platform") == "Shopee" else (row.get("external_id") or row.get("id")),
        "platform": row.get("platform"),
        "name": row.get("name"),
        "price": float(row.get("price") or 0.0),
        "price_before_discount": float(row.get("price_before_discount") or 0.0),
        "discount_rate": float(row.get("discount_rate") or 0.0),
        "affiliate_url": row.get("affiliate_url"),
        "image_url": image_url,
        "images": images,
        "video_url": video_url,
        "status": row.get("status", "Posted")
    }

def load_products_by_date(days: int = 7) -> list[dict]:
    """
    Loads raw products that were posted in the last X days.
    """
    sql = f"""
        SELECT 
            rp.id, rp.platform, rp.external_id, rp.name, rp.price, rp.price_before_discount, 
            rp.affiliate_url, rp.raw_media_urls, rp.discount_rate, rp.sales, ci.status
        FROM raw_products rp
        INNER JOIN content_items ci
        ON rp.id = ci.product_id
        WHERE ci.status = 'Posted'
        AND ci.created_at >= date('now', '-{days} days')
        ORDER BY ci.created_at DESC
    """
    
    results = run_query(sql)
    clean_products = []
    
    for row in results:
        images = []
        video_url = ""
        try:
            if row.get("raw_media_urls"):
                media_data = json.loads(row["raw_media_urls"])
                image_url = media_data.get("image", "")
                images = media_data.get("images", [image_url] if image_url else [])
                video_url = media_data.get("videoUrl", "")
        except json.JSONDecodeError:
            pass
            
        clean_product = {
            "id": row.get("id"),
            "item_id": row.get("external_id") if row.get("platform") == "Shopee" else (row.get("external_id") or row.get("id")),
            "platform": row.get("platform"),
            "name": row.get("name"),
            "price": float(row.get("price") or 0.0),
            "original_price": float(row.get("price_before_discount") or 0.0),
            "discount_rate": float(row.get("discount_rate") or 0.0),
            "affiliate_url": row.get("affiliate_url"),
            "image_url": image_url,
            "images": images,
            "video_url": video_url,
            "status": row.get("status")
        }
        clean_products.append(clean_product)
        
    return clean_products
