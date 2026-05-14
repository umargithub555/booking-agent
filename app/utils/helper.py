import random
import re
import emoji
import bcrypt
from passlib.context import CryptContext
from datetime import datetime,timedelta,timezone

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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





def hash_password(password: str) -> str:
    # Convert password to bytes, salt it, and hash it
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Return as string for database storage
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Compare bytes of plain password against stored hash
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def generate_otp():
    return str(random.randint(100000,999999)) # 6 digit-otp


def get_otp_expire_time(minutes=5):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)