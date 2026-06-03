from cryptography.fernet import Fernet
from django.conf import settings
import base64
from typing import Optional
from django.db import models


class EncryptionService:
    def __init__(self):
        key = getattr(settings, 'FERNET_KEY', None)
        if not key:
            raise ValueError(
                "FERNET_KEY не найден в settings.py. "
                "Добавьте FERNET_KEY = Fernet.generate_key() в настройки."
            )
        
        if isinstance(key, str):
            key = key.encode()
            
        self.cipher = Fernet(key)
    
    def encrypt(self, plain_text: Optional[str]) -> Optional[str]:
        """
        Шифрует текст
        Args:
            plain_text: Исходный текст для шифрования
        Returns:
            Зашифрованный текст в виде строки или None
        """
        if not plain_text:
            return None
            
        try:
            encrypted = self.cipher.encrypt(plain_text.encode())
            return encrypted.decode()
        except Exception as e:
            raise ValueError(f"Ошибка при шифровании: {str(e)}")
    
    def decrypt(self, encrypted_text: Optional[str]) -> Optional[str]:
        """
        Дешифрует текст
        Args:
            encrypted_text: Зашифрованный текст
        Returns:
            Расшифрованный текст или None
        """
        if not encrypted_text:
            return None
            
        try:
            decrypted = self.cipher.decrypt(encrypted_text.encode())
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Ошибка при дешифровании: {str(e)}")


encryption_service = EncryptionService()


def encrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Шифрует значение поля
    """
    return encryption_service.encrypt(value) if value else None


def decrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Дешифрует значение поляъ
    """
    return encryption_service.decrypt(value) if value else None


class EncryptedCharField(models.TextField):
    """
    Кастомное поле для автоматического шифрования/дешифрования
    """
    
    def __init__(self, *args, **kwargs):
        # Увеличиваем max_length для хранения зашифрованных данных
        if 'max_length' in kwargs:
            # Fernet добавляет примерно 60 байт overhead + base64 encoding
            original_length = kwargs['max_length']
            kwargs['max_length'] = original_length * 3
        super().__init__(*args, **kwargs)
    
    def from_db_value(self, value, expression, connection):
        """
        Автоматически дешифрует при чтении из БД
        """
        if value is None:
            return value
        return decrypt_field(value)
    
    def to_python(self, value):
        """
        Преобразование значения в Python объект
        """
        if isinstance(value, str):
            try:
                return decrypt_field(value)
            except:
                return value
        return value
    
    def get_prep_value(self, value):
        """
        Автоматически шифрует перед сохранением в БД
        """
        if value is None:
            return value
        return encrypt_field(value)

class PersonalDataService:
    """
    Сервис для работы с персональными данными с шифрованием
    """
    
    @staticmethod
    def create_renter(first_name: str, last_name: str, 
                      middle_name: Optional[str] = None,
                      phone_number: Optional[str] = None,
                      email: Optional[str] = None):
        """
        Создает арендатора с шифрованием персональных данных
        """
        from .models import Renter
        
        return Renter.objects.create(
            first_name=encrypt_field(first_name),
            last_name=encrypt_field(last_name),
            middle_name=encrypt_field(middle_name),
            phone_number=encrypt_field(phone_number),
            email=encrypt_field(email)
        )
    
    @staticmethod
    def get_decrypted_renter_data(renter_id: int) -> dict:
        """
        Получает расшифрованные данные арендатора
        """
        from .models import Renter
        
        renter = Renter.objects.get(id=renter_id)
        return {
            'id': renter.id,
            'first_name': decrypt_field(renter.first_name),
            'last_name': decrypt_field(renter.last_name),
            'middle_name': decrypt_field(renter.middle_name),
            'phone_number': decrypt_field(renter.phone_number),
            'email': decrypt_field(renter.email),
        }
    
    @staticmethod
    def update_renter(renter_id: int, **kwargs):
        """
        Обновляет данные арендатора с шифрованием
        """
        from .models import Renter
        
        renter = Renter.objects.get(id=renter_id)
        
        # Шифруем персональные данные перед сохранением
        encrypted_fields = {}
        for field, value in kwargs.items():
            if field in ['first_name', 'last_name', 'middle_name', 'phone_number', 'email']:
                encrypted_fields[field] = encrypt_field(value) if value else None
            else:
                encrypted_fields[field] = value
        
        for field, value in encrypted_fields.items():
            setattr(renter, field, value)
        
        renter.save()
        return renter
    
    @staticmethod
    def search_by_decrypted_field(model_class, field_name: str, search_value: str):
        """
        Поиск по зашифрованному полю
        """
        results = []
        for obj in model_class.objects.all():
            encrypted_value = getattr(obj, field_name)
            decrypted_value = decrypt_field(encrypted_value)
            
            if decrypted_value and search_value.lower() in decrypted_value.lower():
                results.append(obj)
        
        return results