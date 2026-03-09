import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from backend.logger import setup_logger

from backend.utils.text_processor import clean_product_name
from dotenv import load_dotenv
load_dotenv(override=True)
logger = setup_logger("script_generator")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CONFIG_PATH = "backend/config/roteiro_config.json"
INTRO_PHRASE = "oi pessoal eu sou a li do achadinhos da li olha o que eu encontrei hoje"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def generate_viral_script(product_data, include_price: bool = True):
    """
    Generates a viral script for the Li avatar using GPT-4o-Mini.
    Specialized for Ultra Economy: 150-180 chars, random intro.
    """
    config = load_config()
    style = config.get("script_style", {})
    intros = config.get("assets", {}).get("intros", [])
    
    import random
    selected_intro = random.choice(intros) if intros else {"phrase": INTRO_PHRASE}
    intro_phrase = selected_intro.get("phrase", INTRO_PHRASE)
    
    # Textual data for AI
    original_name = product_data.get('name', 'produto incrível')
    # Pre-clean the name to remove technical specs like "1182ml"
    clean_name = clean_product_name(original_name)
    
    price_current = product_data.get('current_price', product_data.get('price', ''))
    discount = product_data.get('current_discount', product_data.get('discount_rate', ''))
    
    price_context = f"Preço: R$ {price_current}, Desconto: {discount}%" if include_price else "NÃO mencione preço ou desconto."
    
    system_prompt = f"""
    Você é a Li, influenciadora de Achadinhos.
    O vídeo COMEÇA com o clipe fixo: "{intro_phrase}".
    
    Sua tarefa: Escrever APENAS o corpo (narração do produto) para ElevenLabs.
    
    REGRAS CRÍTICAS DE NARRATIVA:
    1. USE O NOME LIMPO: "{clean_name}". Identifique o NOME DA MARCA e mantenha a grafia EXATA (ex: WATERSY).
    2. NUNCA fale especificações técnicas (ex: 1182ml, 220v). Foque no benefício.
    3. MANTENHA o texto entre 170 e 210 caracteres.
    4. PREÇO E DESCONTO: Se include_price=True, você DEVE dizer: "por apenas [preço] e tá com [desconto]% de desconto".
    5. Estilo: Rápido, direto, minúsculas, sem pontuação excessiva. Sem saudações.
    """
    
    user_prompt = f"Produto Original: {original_name}. {price_context}"

    try:
        logger.info(f"Generating ULTRA ECONOMY script body for {original_name} (Price included: {include_price})...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=100,
            temperature=0.8
        )
        body = response.choices[0].message.content.strip()
        
        # Security Cleaning
        clean_body = body
        for unwanted in [intro_phrase, "oi pessoal", "olha o que eu encontrei", "comenta", "achadinho"]:
            if clean_body.lower().startswith(unwanted.lower()):
                clean_body = clean_body[len(unwanted):].strip()
        
        # Strict enforcement
        if len(clean_body) > 180:
            clean_body = clean_body[:177] + "..."

        logger.info(f"Ultra Economy script body generated ({len(clean_body)} chars).")
        return intro_phrase, clean_body
    except Exception as e:
        logger.error(f"Error generating script: {e}")
        return intro_phrase, f"olha esse achadinho: {clean_name} por {price_current}!"
