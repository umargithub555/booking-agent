import re
import emoji



SENTENCE_ENDINGS = {".", "!", "?"}


def is_sentence_end(text: str) -> bool:
    """True when buffer looks like a complete sentence."""
    stripped = text.rstrip()
    return len(stripped) > 10 and stripped[-1] in SENTENCE_ENDINGS


def clean_for_tts(text: str) -> str:
    """Remove markdown symbols and extra punctuation for cleaner speech."""
    # Remove markdown bold/italic/code symbols
    text = re.sub(r'[*_`#>-]+', '', text)

    # Remove URLs
    text = re.sub(r'http\S+|www\.\S+', '', text)

    # Remove emojis
    text = emoji.replace_emoji(text, replace='')

    # Remove extra punctuation sequences
    text = re.sub(r'[^\w\s.,!?]', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text