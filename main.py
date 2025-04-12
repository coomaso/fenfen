from Crypto.Cipher import AES
import base64

# Here's the actual key string being parsed as UTF-8
key_str = "6875616E6779696E6875616E6779696E"  # not hex parsed!
key = key_str.encode("utf-8")                # 32 bytes (AES-256)

iv = b"sskjKingFree5138"                     # 16 bytes

def decrypt_no_padding(ciphertext_b64):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = base64.b64decode(ciphertext_b64)
    decrypted = cipher.decrypt(raw)
    return decrypted.rstrip(b"\x00").decode("utf-8")

# Example usage
enc_data = "AvOdaO5jeXZVTKm8pPtntmrjNVZg0gBbwvWUFjB71XgfCf6Rr+VLneGdnrQdAKGh"  # your base64-encoded ciphertext
print(decrypt_no_padding(enc_data))
