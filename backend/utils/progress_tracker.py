import json
import os
import time

PROGRESS_DIR = "temp/progress"

def update_progress(product_id, step, percentage, message):
    """
    Updates a JSON file with the current generation progress.
    """
    if not os.path.exists(PROGRESS_DIR):
        os.makedirs(PROGRESS_DIR)
        
    data = {
        "product_id": product_id,
        "step": step,
        "percentage": percentage,
        "message": message,
        "timestamp": time.time()
    }
    
    filepath = os.path.join(PROGRESS_DIR, f"{product_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_progress(product_id):
    """Reads the current progress for a product."""
    filepath = os.path.join(PROGRESS_DIR, f"{product_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"status": "not_found"}
