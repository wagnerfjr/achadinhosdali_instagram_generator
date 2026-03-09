import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from backend.logger import setup_logger

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
    product_name = product_data.get('name', 'produto incrível')
    price_current = product_data.get('current_price', product_data.get('price', ''))
    discount = product_data.get('current_discount', product_data.get('discount_rate', ''))
    
    price_context = f"Preço: {price_current}, Desconto: {discount}%" if include_price else "NÃO mencione preço ou desconto."
    
    system_prompt = f"""
    Você é a Li, influenciadora de Achadinhos.
    O vídeo COMEÇA com o clipe fixo: "{intro_phrase}".
    
    Sua tarefa: Escrever APENAS o corpo (narração do produto) para ElevenLabs.
    
    REGRAS DE IMPACTO E ECONOMIA:
    1. MÁXIMO de 180 caracteres. Mantenha entre 150 e 180 chars.
    2. Estrutura: Nome do Produto -> Por que é viral/bom -> Chamada de curiosidade.
    3. NO VÍDEO: {price_context}
    4. NÃO inclua "comenta achadinho", "link na bio" ou saudações de entrada/saída.
    5. O ritmo deve ser rápido e direto.
    6. Texto em minúsculas, sem pontuação excessiva.
    """
    
    user_prompt = f"Produto: {product_name}. {price_context}"

    try:
        logger.info(f"Generating ULTRA ECONOMY script body for {product_name} (Price included: {include_price})...")
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
        return intro_phrase, f"olha esse achadinho: {product_name} por {price_current}!"
