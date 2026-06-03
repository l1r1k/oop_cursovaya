from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re


# Валидатор для номера телефона
phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Номер телефона должен быть в формате: '+999999999'. Допускается до 15 цифр."
)


def validate_phone_number(value):
    """
    Валидатор для российских номеров телефонов
    """
    if not value:
        return
    
    cleaned = re.sub(r'[^\d+]', '', value)
    
    # Допустимые форматы
    patterns = [
        r'^\+7\d{10}$',  # +7XXXXXXXXXX
        r'^8\d{10}$',    # 8XXXXXXXXXX
        r'^7\d{10}$',    # 7XXXXXXXXXX
    ]
    
    if not any(re.match(pattern, cleaned) for pattern in patterns):
        raise ValidationError(
            'Введите корректный номер телефона в формате +7XXXXXXXXXX, 8XXXXXXXXXX или 7XXXXXXXXXX'
        )

def validate_costume_cost(value):
    """
    Валидатор введенной стоимости костюма
    """
    if not value:
        raise ValidationError('Стоимость аренды не может быть пустой')
    
    if value < 0:
        raise ValidationError('Стоимость аренды не может быть отрицательной')

    if value > 999999.99:
        raise ValidationError('Стоимость аренды не может быть больше 999999.00 руб.')

def validate_inventory_code(value):
    """
    Валидатор инвентарного кода
    """
    if not value:
        raise ValidationError('Инвентарный код не может быть пустым')
    
    if not re.match(r'^[0-9]+$', value):
        raise ValidationError(
            'Инвентарный код может содержать только цифры'
        )
    
    if len(value) > 14:
        raise ValidationError('Инвентарный код не может быть длиннее 14 символов')
    
    if len(value) < 14:
        raise ValidationError('Инвентарный код не может быть короче 14 символов')


def validate_hex_color(value):
    """
    Валидатор HEX кода цвета
    """
    if not value:
        return
    
    if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
        raise ValidationError(
            'Введите корректный HEX код цвета в формате #RRGGBB (например, #FF5733)'
        )


def validate_email_domain(value):
    """
    Дополнительный валидатор проверки домена email
    """
    if not value:
        return
    
    if '@' not in value:
        raise ValidationError('Email должен содержать символ @')
    
    domain = value.split('@')[-1]
    
    if not domain or '.' not in domain:
        raise ValidationError('Введите корректный email адрес')


def validate_age_range(min_age, max_age):
    """
    Валидатор проверки диапазона возрастов.
    """
    if min_age < 0:
        raise ValidationError({'min_age': 'Минимальный возраст не может быть отрицательным'})
    
    if max_age < 0:
        raise ValidationError({'max_age': 'Максимальный возраст не может быть отрицательным'})
    
    if min_age > max_age:
        raise ValidationError({
            'max_age': 'Максимальный возраст не может быть меньше минимального'
        })
    
    if max_age > 150:
        raise ValidationError({'max_age': 'Максимальный возраст не может превышать 150 лет'})


def validate_costume_count(value):
    """
    Валидатор количества костюмов
    """
    if value < 0:
        raise ValidationError('Количество не может быть отрицательным')
    
    if value > 1000:
        raise ValidationError('Количество не может превышать 1000 единиц')


def validate_rent_dates(date_start, time_start, date_end, time_end):
    """
    Валидатор проверки дат и времени аренды
    """
    from datetime import timedelta
    
    if date_end < date_start:
        raise ValidationError({
            'date_end': 'Дата окончания не может быть раньше даты начала'
        })
    
    if date_end == date_start:
        if time_end <= time_start:
            raise ValidationError({
                'time_end': 'Время окончания должно быть позже времени начала'
            })
    
    max_duration = timedelta(days=30)
    duration = date_end - date_start
    
    if duration > max_duration:
        raise ValidationError({
            'date_end': f'Максимальная длительность аренды - {max_duration.days} дней'
        })


def validate_image_size(image):
    """
    Валидатор размера загружаемого изображения.
    """
    max_size_mb = 5
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if image.size > max_size_bytes:
        raise ValidationError(
            f'Размер файла не должен превышать {max_size_mb} МБ. '
            f'Текущий размер: {round(image.size / (1024 * 1024), 2)} МБ'
        )
    
    try:
        from PIL import Image
        img = Image.open(image)
        width, height = img.size
        
        max_width = 4000
        max_height = 4000
        
        if width > max_width or height > max_height:
            raise ValidationError(
                f'Разрешение изображения не должно превышать {max_width}x{max_height} пикселей. '
                f'Текущее разрешение: {width}x{height}'
            )
    except Exception as e:
        raise ValidationError(f'Ошибка при обработке изображения: {str(e)}')


def validate_photo_format(image):
    """
    Валидатор формата изображения
    """
    allowed_formats = ['JPEG', 'JPG', 'PNG', 'WEBP']
    
    try:
        from PIL import Image
        img = Image.open(image)
        
        if img.format.upper() not in allowed_formats:
            raise ValidationError(
                f'Неподдерживаемый формат изображения: {img.format}. '
                f'Разрешены: {", ".join(allowed_formats)}'
            )
    except Exception as e:
        raise ValidationError(f'Ошибка при проверке формата изображения: {str(e)}')


class UniqueInventoryCodeValidator:
    """
    Валидатор проверки уникальности инвентарного кода
    """
    
    def __init__(self, model_class):
        self.model_class = model_class
    
    def __call__(self, value, instance=None):
        queryset = self.model_class.objects.filter(inventory_code=value)
        
        if instance and instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        
        if queryset.exists():
            raise ValidationError(
                f'Костюм с инвентарным кодом "{value}" уже существует'
            )


def validate_request_item_quantity(costume, quantity):
    """
    Валидатор проверки количества костюмов в заявке
    """
    if quantity < 1:
        raise ValidationError('Количество должно быть больше 0')
    
    if quantity > costume.count:
        raise ValidationError(
            f'Запрошенное количество ({quantity}) превышает доступное ({costume.count})'
        )


def validate_future_date(value):
    """
    Валидатор проверки что дата в будущем
    """
    from datetime import date
    
    if value < date.today():
        raise ValidationError('Дата не может быть в прошлом')


def validate_past_or_today_date(value):
    """
    Валидатор проверки что дата в прошлом или сегодня
    """
    from datetime import date
    
    if value > date.today():
        raise ValidationError('Дата не может быть в будущем')