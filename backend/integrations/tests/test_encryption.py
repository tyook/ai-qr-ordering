from integrations.encryption import encrypt_token, decrypt_token


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "sk_live_abc123_very_secret"
        encrypted = encrypt_token(plaintext)
        assert encrypted != plaintext
        assert decrypt_token(encrypted) == plaintext

    def test_encrypt_empty_string(self):
        assert encrypt_token("") == ""
        assert decrypt_token("") == ""

    def test_encrypted_output_is_different_each_time(self):
        plaintext = "test_token"
        e1 = encrypt_token(plaintext)
        e2 = encrypt_token(plaintext)
        assert e1 != e2
        assert decrypt_token(e1) == plaintext
        assert decrypt_token(e2) == plaintext
