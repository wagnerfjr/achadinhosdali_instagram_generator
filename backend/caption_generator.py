from openai import OpenAI
from dotenv import load_dotenv
from .logger import setup_logger
import os

logger = setup_logger("caption_gen")

load_dotenv()

client = None
if os.getenv("OPENAI_API_KEY"):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def optimize_title(raw_name: str) -> str:
    """Uses OpenAI to shorten and optimize the product name."""
    if not client:
        return raw_name
    
    if len(raw_name) <= 35:
        return raw_name
        
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Você é um copywriter de e-commerce de elite. Transforme o título do produto em um nome curto e amigável de no MÁXIMO 5 palavras. Apenas retorne o nome, sem aspas ou pontuação."},
                {"role": "user", "content": raw_name}
            ],
            max_tokens=50
        )
        optimized = response.choices[0].message.content.strip()
        return optimized if optimized else raw_name
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return raw_name

def generate_promotional_phrase(product: dict) -> str:
    """Generate promotional phrase based on product data (Elite Rules)"""
    discount = float(product.get("discount_rate", 0))
    sales = int(product.get("sales", 0))
    
    if discount >= 50:
        return "🔥 METADE DO PREÇO 😱"
    elif discount >= 30:
        return "🔥 No precinho 😱"
    elif discount >= 20:
        return "💰 Oferta imperdível 🎯"
    
    if sales > 1000:
        return "⭐ Mais vendido do mês 🚀"
    elif sales > 500:
        return "🔥 Queridinho da galera 💜"
    
    return "✨ Oferta especial 🎁"

def generate_caption(product: dict, feedback: str = None, style: str = "standard") -> str:
    """
    Generates a premium promotional caption for a product.
    Supports 'standard' and 'influencer' styles.
    """
    raw_name = product.get("name", "Produto incrível")
    name = optimize_title(raw_name)
    
    price = product.get("price", 0)
    price_before = product.get("price_before_discount", price)
    
    platform = product.get("platform", "Shopee").lower()
    phrase = generate_promotional_phrase(product)
    
    # Format prices as currency string
    price_str = f"R${price:.2f}".replace('.', ',')
    price_before_str = f"R${price_before:.2f}".replace('.', ',')
    
    if style == "influencer":
        # Influencer style (Li)
        caption = f"✨ OII GENTE! Olha esse achadinho que a Li separou pra vocês! 😍\n\n"
        caption += f"🌈 {name}\n\n"
        caption += f"💥 Tá rolando uma promo insana na {platform.capitalize()}!\n"
        if price_before > price:
            caption += f"💰 De {price_before_str} por apenas {price_str}!! 😱\n\n"
        else:
            caption += f"✅ Por apenas {price_str}! ✨\n\n"
        
        caption += "🔗 O LINK tá na BIO ou me chama no DIRECT com a palavra 'QUERO' que eu te mando! 💜\n\n"
        caption += f"#achadinhosdali #li #influencer #{platform} #ofertaboa"
        return caption

    # Build Standard Post
    caption = f"💰 {phrase}\n"
    caption += f"📦 {name}\n\n"
    
    if price_before > price:
        caption += f"💰 De {price_before_str}\n"
        caption += f"✅ Por {price_str} 🔥\n\n"
    else:
        caption += f"✅ Por apenas {price_str}! ✨\n\n"
        
    if feedback:
        caption += f"📝 Nota: {feedback}\n\n"
        
    caption += "🔗 COMPRAR AQUI: Link na bio\n\n"
    caption += "👉 Galera, comprando pelo link você ajuda o canal! 🙏\n\n"
    
    caption += f"#achadinhos #promoção #{platform} #oferta #compras"
    
    return caption
def generate_seo_caption(product: dict, format_type: str = "reels") -> str:
    """
    Generates a high-converting, SEO-optimized caption using GPT-4o-Mini.
    Ensures NO PRICE or DISCOUNT is mentioned to avoid legal issues.
    """
    if not client:
        # Fallback to standard if no API key
        return generate_caption(product, style="influencer" if format_type == "stories" else "standard")

    raw_name = product.get("name", "Produto incrível")
    platform = product.get("platform", "Shopee").capitalize()
    
    # Advanced Prompting for Elite Affiliate Results
    system_prompt = f"""
    Você é um Copywriter de E-commerce Nível Sênior, especialista em marketing de afiliados no Brasil.
    Sua missão é criar uma legenda IRRESISTÍVEL para um post de {format_type.upper()} no Instagram.

    PROIBIÇÕES CRÍTICAS:
    1. NUNCA mencione preço (R$) ou valor numérico.
    2. NUNCA mencione porcentagem de desconto (%).
    3. NUNCA mencione "oferta expira" ou prazos específicos.
    
    REGRAS DE OURO:
    - Use gatilhos mentais: Curiosidade, Escassez (sem citar tempo), Prova Social ou Pertencimento.
    - Comece com um HOOK (Gancho) matador na primeira linha.
    - Tom de voz: Influenciador amigável, animado e autêntico (Persona: Li do Achadinhos).
    - Formatação: Use emojis estrategicamente, quebras de linha para leitura escaneável.
    - CTA: Direcione para o Link na BIO ou para comentar "EU QUERO".

    ESTRUTURA POR FORMATO:
    - REELS: Foco em viralidade, curiosidade sobre o benefício do produto. Link na Bio.
    - STORIES: Foco em proximidade, "olha o que eu achei", urgência de "vê logo antes que acabe".
    
    HASHTAGS (Clusterizados):
    Inclua 20 hashtags divididas em: 5 de alto alcance, 5 nicho, 5 genéricas de achadinhos, 5 sobre a plataforma ({platform}).
    Use 20 hashtags total
    Faça um mix entre alto alcance, nicho, viral e genericas de achadinhos
    Priorize hashtags relacionadas a "achadinhos", "moda feminina", "compras online"
    Evite repetir a mesma combinação de hashtags em todos os posts
    E principalmente sempre inclua a hashtag #achadinhosdali
    """

    user_prompt = f"Produto: {raw_name}\nPlataforma: {platform}\nContexto: Gere uma legenda que gere desejo imediato sem citar preços."

    try:
        logger.info(f"Generating SEO POWER CAPTION for {format_type}...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.85
        )
        caption = response.choices[0].message.content.strip()
        
        # Anti-price safety filter (regex/string check)
        import re
        caption = re.sub(r'R\$\s?[\d,.]+', '', caption) # Remove any accidentally generated prices
        caption = re.sub(r'\d+%', '', caption) # Remove any accidentally generated percentages
        
        return caption
    except Exception as e:
        logger.error(f"SEO Caption UI Error: {e}")
        return generate_caption(product, style="influencer" if format_type == "stories" else "standard")
