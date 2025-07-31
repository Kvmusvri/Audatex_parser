"""
Тест токенов
"""
from core.security.auth_utils import hash_token, generate_secure_token

# Генерируем токен как при создании сессии
token = generate_secure_token()
print(f"Сгенерированный токен: {token}")
print(f"Хеш токена: {hash_token(token)}")

# Проверяем, что хеш совпадает
token_hash = hash_token(token)
print(f"Проверка хеша: {hash_token(token) == token_hash}") 