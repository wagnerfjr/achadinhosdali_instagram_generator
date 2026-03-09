import hmac
import hashlib
import time
import json
import requests
import os
from typing import List, Optional
from dotenv import load_dotenv
from .logger import setup_logger

logger = setup_logger("shopee_api")

load_dotenv()

class ShopeeAffiliateClient:
    def __init__(self):
        self.app_id = os.getenv("SHOPEE_APP_ID")
        self.secret = os.getenv("SHOPEE_SECRET")
        self.base_url = "https://open-api.affiliate.shopee.com.br/graphql"

    def _sign_request(self, payload_string: str, timestamp: int):
        """
        SIGNATURE METHOD
        string(AppId) + string(Timestamp) + payload_string + Secret
        """
        sign_base = f"{self.app_id}{timestamp}{payload_string}{self.secret}"
        signature = hashlib.sha256(sign_base.encode("utf-8")).hexdigest()
        
        header = f"SHA256 Credential={self.app_id}, Timestamp={timestamp}, Signature={signature}"
        return header

    def _send_request(self, payload: dict):
        """
        Centralized method for sending POST requests to Shopee's GraphQL API.
        """
        payload_string = json.dumps(payload, separators=(',', ':')) # No extra spaces
        timestamp = int(time.time())
        header_auth = self._sign_request(payload_string, timestamp)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": header_auth
        }
        
        try:
            response = requests.post(self.base_url, data=payload_string, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"Shopee API GraphQL Error: {data['errors']}")
            
            return data.get("data", {})
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Shopee API Connection Error: {str(e)}")

    def generate_affiliate_link(self, original_url: str, sub_ids: List[str] = None):
        """
        Mutation GraphQL generateShortLink with input object
        """
        mutation = """
        mutation ($input: ShortLinkInput!) {
            generateShortLink (input: $input) {
                shortLink
            }
        }
        """
        variables = {
            "input": {
                "originUrl": original_url,
                "subIds": sub_ids or []
            }
        }
        
        data = self._send_request({
            "query": mutation,
            "variables": variables
        })
        
        short_link = data.get("generateShortLink", {}).get("shortLink")
        return short_link

    def get_item_info(self, item_id: str):
        """
        Query for product info using item_id (must be numeric).
        Bug in Shopee API: Sending Int64 as a variable fails. 
        Solution: Embed directly in query string.
        """
        try:
            numeric_id = int(item_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid numeric item_id: {item_id}. Skipping Shopee API call.")
            return None

        # Embed ID directly to avoid "wrong type" variable bug
        query = f"""
        {{
            productOfferV2 (itemId: {numeric_id}) {{
                nodes {{
                    itemId
                    productName
                    offerLink
                    imageUrl
                    priceMin
                    priceDiscountRate
                    sales
                    ratingStar
                }}
            }}
        }}
        """
        
        data = self._send_request({"query": query})
        nodes = data.get("productOfferV2", {}).get("nodes", [])
        return nodes[0] if nodes else None
