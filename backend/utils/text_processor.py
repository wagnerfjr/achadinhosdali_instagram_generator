import re

def format_currency_to_speech(value_str):
    """
    Converts currency strings or floats to natural mouth-friendly Portuguese.
    Ex: R$ 34,90 -> "trinta e quatro reais e noventa"
    """
    try:
        # Pre-cleanup: remove R$, dots, and normalize decimal separator
        clean_val = str(value_str).replace('R$', '').replace('.', '').replace(',', '.')
        value = float(clean_val)
        
        reais = int(value)
        centavos = int(round((value - reais) * 100))
        
        texto_reais = f"{reais} reais" if reais != 1 else "um real"
        
        if centavos == 0:
            return texto_reais
        elif centavos == 50:
            return f"{texto_reais} e cinquenta"
        else:
            return f"{texto_reais} e {centavos}"
    except Exception:
        return str(value_str)

def format_numbers_to_speech(text):
    """
    Generic number to speech formatter for ratings and counts.
    Ex: 4.8 stars -> "quase cinco estrelas"
    """
    if not text: return ""
    
    # 1. Prices: R$ 34,90 -> trinta e quatro reais e noventa
    text = re.sub(r'R\$\s?(\d+([.,]\d+)?)', lambda m: format_currency_to_speech(m.group(0)), text)
    
    # 2. Ratings: 4.8 estrelas -> quase 5 estrelas / 4,3 estrelas -> 4 estrelas e meia
    def _replace_stars(m):
        try:
            val_int = int(m.group(1))
            val_dec = int(m.group(2))
            if val_dec >= 7:
                return f"quase {val_int + 1} estrelas"
            else:
                return f"{val_int} estrelas e meia"
        except (ValueError, IndexError):
            return m.group(0)

    text = re.sub(r'(\d)[.,](\d)\s?estrelas', _replace_stars, text)
    
    return text

def clean_product_name(name):
    """Removes SKUs and corporate terms from titles."""
    name = re.sub(r'[A-Z0-9]{5,}-\w+', '', name) # Remove common SKU patterns
    name = re.sub(r'\(.*?\)', '', name) # Remove parenthetical info
    return name.strip()
