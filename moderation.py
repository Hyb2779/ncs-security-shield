import os
import re

WORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'banned_words.txt')

def _load_words():
    with open(WORDS_FILE, 'r', encoding='utf-8') as f:
        words = [w.strip() for w in f.readlines() if w.strip()]
    return words

def _normalize(text):
    # Turkce buyuk/kucuk harf tutarliligi icin ozel donusum
    text = text.replace('İ', 'i').replace('I', 'ı')
    return text.lower()

def _build_pattern():
    words = _load_words()
    words_sorted = sorted(words, key=len, reverse=True)
    escaped = [re.escape(_normalize(w)) for w in words_sorted]
    # Kelime/ifade siniri: once/sonra harf-rakam olmayan bir karakter (ya da metin basi/sonu)
    pattern = r'(?<![^\W\d_])(?:' + '|'.join(escaped) + r')(?![^\W\d_])'
    return re.compile(pattern, re.UNICODE)

_PATTERN = _build_pattern()

def reload_words():
    global _PATTERN
    _PATTERN = _build_pattern()

def find_banned_word(text):
    if not text:
        return None
    normalized = _normalize(text)
    match = _PATTERN.search(normalized)
    return match.group(0) if match else None
