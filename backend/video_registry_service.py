import os
import requests
from .logger import setup_logger

logger = setup_logger("video_registry")

# Configured via .env: VIDEO_REGISTRY_URL
DEFAULT_REGISTRY_URL = "https://liachadinhos.com.br/api/videos/register"


def register_video(
    product_id: str,
    google_drive_file_id: str,
    nome_arquivo: str,
    affiliate_link: str = None,
    platform_target: str = "Instagram",
    duracao_segundos: int = None,
    resolucao: str = "1080x1920",
    tamanho_bytes: int = None,
    modelo_ia: str = "conteudo-factory",
    generation_params: dict = None,
) -> bool:
    """
    Registers a generated video in the Achadinhos external system.
    Returns True on success, False on failure (non-blocking).
    """
    registry_url = os.getenv("VIDEO_REGISTRY_URL", DEFAULT_REGISTRY_URL)
    token = os.getenv("MELI_SECRET")
    if not token:
        logger.warning("MELI_SECRET not set — skipping video registry.")
        return False

    payload = {
        "product_id": product_id,
        "google_drive_file_id": google_drive_file_id,
        "nome_arquivo": nome_arquivo,
        "platform_target": platform_target,
        "resolucao": resolucao,
        "modelo_ia": modelo_ia,
    }

    # Optional fields — only include if provided
    if affiliate_link:
        payload["affiliate_link"] = affiliate_link
    if duracao_segundos is not None:
        payload["duracao_segundos"] = duracao_segundos
    if tamanho_bytes is not None:
        payload["tamanho_bytes"] = tamanho_bytes
    if generation_params:
        payload["generation_params"] = generation_params

    headers = {
        "Content-Type": "application/json",
        "x-war-token": token,
    }

    try:
        resp = requests.post(registry_url, json=payload, headers=headers, timeout=15)
        if resp.status_code in (200, 201):
            logger.info(f"Video registered successfully. product_id={product_id}, drive_id={google_drive_file_id}")
            return True
        else:
            logger.warning(
                f"Video registry returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
            return False
    except requests.exceptions.Timeout:
        logger.error(f"Video registry timeout for product_id={product_id}")
        return False
    except Exception as e:
        logger.error(f"Video registry error for product_id={product_id}: {e}")
        return False
