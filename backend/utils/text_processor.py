import re

def format_currency_to_speech(value_str):
    """
    Converts currency strings or floats to natural mouth-friendly Portuguese.
    Ex: R$ 34,90 -> "trinta e quatro e noventa"
    """
    try:
        # Pre-cleanup: remove R$, dots, and normalize decimal separator
        clean_val = str(value_str).replace('R$', '').replace('.', '').replace(',', '.')
        value = float(clean_val)
        
        reais = int(value)
        centavos = int(round((value - reais) * 100))
        
        # Conversational style: "trinta e quatro reais" if no cents, 
        # "trinta e quatro e noventa" if there are cents.
        if centavos == 0:
            return f"{reais} reais" if reais != 1 else "um real"
        else:
            # For prices, we usually say "sessenta e cinco e quarenta"
            return f"{reais} e {centavos:02d}" # :02d ensures "noventa" for 90, not "9"
    except Exception:
        return str(value_str)

def format_numbers_to_speech(text):
    """
    Generic number to speech formatter for prices, percentages, and ratings.
    """
    if not text: return ""
    
    # 1. Prices with R$: R$ 34,90 or r$ 34,90 -> trinta e quatro e noventa
    text = re.sub(r'[Rr]\$\s?(\d+([.,]\d+)?)', lambda m: format_currency_to_speech(m.group(1)), text)
    
    # 2. Raw prices (numbers with decimal comma): 34,90 -> trinta e quatro e noventa
    # Look for [number],[two-digits] that aren't parts of other things
    text = re.sub(r'\b(\d+(?:,\d{2}))\b', lambda m: format_currency_to_speech(m.group(1)), text)

    # 3. Percentages: 40% -> quarenta por cento
    text = re.sub(r'(\d+)%', r'\1 por cento', text)
    
    # 4. Ratings: 4.8 estrelas -> quase 5 estrelas
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
    """
    Removes SKUs, measurements (ml, g, kg, etc.), and corporate terms from titles.
    Designed to make the text mouth-friendly for AI narration.
    """
    if not name: return ""
    
    # 1. Remove SKUs: A123-BC or similar serials
    name = re.sub(r'[A-Z0-9]{5,}-\w+', '', name)
    
    # 2. Remove Parentheses or Brackets (usually technical info)
    name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name)
    
    # 3. Remove typical tech specs: 1182ml, 220v, 500g, 4k, 128gb, 10pos, 5x, 30cm, etc.
    # We look for numbers immediately followed by units (case insensitive)
    name = re.sub(r'(?i)\b\d+(?:\.\d+)?\s?(?:ml|g|kg|cm|mm|px|v|ah|w|mah|gb|tb|oz|st|unid|pçs|pcs|hz|k|x)\b', '', name)
    
    # 4. Remove excessive whitespaces/punctuation
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'([-\|/,])\s*\1+', r'\1', name) # dedup separators
    
    return name.strip()
