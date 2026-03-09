import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.curdir))

from backend.utils.script_generator import generate_viral_script
from backend.utils.text_processor import format_numbers_to_speech

# Mock output for user verification
def run_test():
    load_dotenv(override=True)
    
    # Using the Watersy Cup example provided by the user
    product_data = {
        "id": "0c347367a36141d4bc643eabc8209b36",
        "name": "Cortina Blackout PVC Com Tecido voil xadrez 1 parte 1,40 × 1,70 / 2,00 X 1,40 PROMOÇÃO INPERDIVEL",
        "price": 46.8,
        "current_price": 65.4,
        "discount_rate": 48.0,
        "current_discount": 40.0
    }

    print("--- SIMULAÇÃO DE NARRAÇÃO (CUSTO ZERO) ---")
    print(f"Produto: {product_data['name']}")
    print(f"Preço: R$ {product_data['price']} | Desconto: {product_data['discount_rate']}%")
    print("-" * 40)

    # 1. Generate Script
    intro, body = generate_viral_script(product_data, include_price=True)
    
    print("\n[PARTES PRÉ-GRAVADAS (CUSTO ZERO - NÃO VAI PARA ELEVENLABS)]: ")
    print(f"INTRO: {intro}")
    print(f"CTA: (Clipe de fechamento aleatório)")
    
    # 2. Format for Speech
    speech_text = format_numbers_to_speech(body)
    
    print("\n[TEXTO ENVIADO PARA ELEVENLABS (CONSUMO DE CRÉDITOS)]: ")
    print(">>> " + speech_text)
    print("\n" + "-" * 40)
    print("OBS: O custo de créditos ocorre APENAS para o texto acima (corpo do produto).")

if __name__ == "__main__":
    run_test()
