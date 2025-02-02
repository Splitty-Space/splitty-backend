import hmac
import hashlib
import string

from config import SECRET_KEY


def generate_referral_code(user_id: int) -> str:
    # Convert user_id to bytes
    user_id_bytes = str(user_id).encode()

    # Create HMAC-SHA256 digest using secret key
    digest = hmac.new(
        key=SECRET_KEY.encode(),
        msg=user_id_bytes,
        digestmod=hashlib.sha256
    ).digest()

    # Define allowed characters (uppercase + digits)
    alphabet = string.ascii_uppercase + string.digits

    # Generate code by converting digest bytes to indices
    referral_code = []
    for i in range(11):  # 11-character code
        # Use modulo to map byte value to [0-35]
        byte_value = digest[i]  # Uses different bytes for each character
        index = byte_value % 36
        referral_code.append(alphabet[index])

    return ''.join(referral_code)
