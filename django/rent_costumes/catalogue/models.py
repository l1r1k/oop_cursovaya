from django.db import models
from django.db.models import Q, CheckConstraint
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .encryption import EncryptedCharField, decrypt_field
from .validators import (
    validate_phone_number,
    validate_photo_format,
    validate_image_size,
    validate_inventory_code,
    validate_costume_count,
    validate_rent_dates,
    validate_request_item_quantity,
    validate_costume_cost
)

from uuid import uuid4


class MaterialClassification(models.Model):
    """Классификация материалов"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название классификации материала",
        unique=True
    )

    class Meta:
        db_table = 'material_classification'
        verbose_name = 'Классификация материала'
        verbose_name_plural = 'Классификации материалов'
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    """Материалы"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название материала",
        unique=True
    )
    classification = models.ForeignKey(
        MaterialClassification,
        on_delete=models.PROTECT,
        related_name='materials',
        verbose_name="Классификация материала"
    )

    class Meta:
        db_table = 'material'
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['name']

    def __str__(self):
        return self.name

class ColorClassification(models.Model):
    """Классификация цвета"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название классификации цвета",
        unique=True
    )

    class Meta:
        db_table = 'color_classification'
        verbose_name = 'Классификация цвета'
        verbose_name_plural = 'Классификации цветов'
        ordering = ['name']

    def __str__(self):
        return self.name

class Color(models.Model):
    """Цвета"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название цвета",
        unique=True
    )
    hex_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        verbose_name="HEX код цвета",
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message='Введите корректный HEX код цвета (например, #FF5733)'
            )
        ],
        help_text="Формат: #RRGGBB"
    )
    classification = models.ForeignKey(
        ColorClassification,
        on_delete=models.PROTECT,
        related_name='colors',
        verbose_name="Классификация цвета"
    )

    class Meta:
        db_table = 'color'
        verbose_name = 'Цвет'
        verbose_name_plural = 'Цвета'
        ordering = ['name']

    def __str__(self):
        return self.name


class CostumeSize(models.Model):
    """Размеры костюмов"""
    label = models.CharField(
        max_length=50,
        verbose_name="Обозначение размера",
        unique=True
    )
    min_age = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Минимальный возраст",
        validators=[MaxValueValidator(150)]
    )
    max_age = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Максимальный возраст",
        validators=[MaxValueValidator(150)]
    )
    is_child = models.BooleanField(
        verbose_name="Детский размер"
    )

    class Meta:
        db_table = 'costume_size'
        verbose_name = 'Размер костюма'
        verbose_name_plural = 'Размеры костюмов'
        ordering = ['min_age', 'label']
        constraints = [
            CheckConstraint(
                condition=Q(min_age__lte=models.F('max_age')),
                name='min_age_lte_max_age'
            ),
            CheckConstraint(
                condition=Q(min_age__gte=0) & Q(max_age__gte=0),
                name='ages_non_negative'
            )
        ]

    def clean(self):
        if self.min_age > self.max_age:
            raise ValidationError({
                'max_age': 'Максимальный возраст не может быть меньше минимального'
            })

    def __str__(self):
        return f"{self.label} ({self.min_age}-{self.max_age} лет)"


class HoldPlace(models.Model):
    """Места хранения"""
    name = models.CharField(
        max_length=256,
        verbose_name="Название места хранения",
        unique=True
    )
    photo = models.ImageField(
        upload_to='hold_places/%Y/%m/',
        verbose_name="Фотография места хранения",
        help_text="Загрузите фотографию места хранения"
    )

    class Meta:
        db_table = 'hold_place'
        verbose_name = 'Место хранения'
        verbose_name_plural = 'Места хранения'
        ordering = ['name']

    def clean(self):
        validate_photo_format(self.photo)
        validate_image_size(self.photo)

    def __str__(self):
        return self.name


class CreativeCollective(models.Model):
    """Творческие коллективы"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название творческого коллектива",
        unique=True
    )

    class Meta:
        db_table = 'creative_collective'
        verbose_name = 'Творческий коллектив'
        verbose_name_plural = 'Творческие коллективы'
        ordering = ['name']

    def __str__(self):
        return self.name


class CostumeClassification(models.Model):
    """Классификация костюмов (иерархическая)"""
    name = models.CharField(
        max_length=50,
        verbose_name="Название классификации"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='children',
        verbose_name="Родительская категория",
        help_text='Указывается в том случае, когда добавляемая классификация является подклассификацией. Например, драмматические постановки - подклассификация для театральных костюмов. Если указывается основная классификация - оставьте поле пустым.'
    )

    class Meta:
        db_table = 'costume_classification'
        verbose_name = 'Классификация костюма'
        verbose_name_plural = 'Классификации костюмов'
        ordering = ['name']
        unique_together = [['name', 'parent']]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class Season(models.Model):
    """Сезоны"""
    SEASON_CHOICES = [
        ('Зима', 'Зима'),
        ('Весна', 'Весна'),
        ('Лето', 'Лето'),
        ('Осень', 'Осень'),
        ('Всесезонный', 'Всесезонный'),
    ]
    
    name = models.CharField(
        max_length=11,
        choices=SEASON_CHOICES,
        verbose_name="Название сезона",
        unique=True
    )

    class Meta:
        db_table = 'season'
        verbose_name = 'Сезон'
        verbose_name_plural = 'Сезоны'
        ordering = ['name']

    def __str__(self):
        return self.name


class Gender(models.Model):
    """Пол"""
    GENDER_CHOICES = [
        ('Мужской', 'Мужской'),
        ('Женский', 'Женский'),
        ('Мальчик', 'Мальчик'),
        ('Девочка', 'Девочка'),
        ('Унисекс', 'Унисекс'),
    ]
    
    name = models.CharField(
        max_length=7,
        choices=GENDER_CHOICES,
        verbose_name="Пол",
        unique=True
    )

    class Meta:
        db_table = 'gender'
        verbose_name = 'Пол'
        verbose_name_plural = 'Пол'
        ordering = ['name']

    def __str__(self):
        return self.name

def generate_uuid():
    return uuid4().__str__()

class GrantPerson(models.Model):
    """Ответственные лица (материально-ответственные)"""
    uuid = models.CharField(
        max_length=36,
        verbose_name="UUID",
        default=generate_uuid,
        editable=False
    )
    last_name = EncryptedCharField(
        max_length=100,
        verbose_name="Фамилия"
    )
    first_name = EncryptedCharField(
        max_length=100,
        verbose_name="Имя"
    )
    middle_name = EncryptedCharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Отчество"
    )
    phone_number = EncryptedCharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Номер телефона"
    )
    email = EncryptedCharField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name="Электронная почта"
    )

    class Meta:
        db_table = 'grant_person'
        verbose_name = 'Ответственное лицо'
        verbose_name_plural = 'Ответственные лица'
        ordering = ['last_name', 'first_name']

    def clean(self):
        validate_phone_number(self.phone_number)

    def __str__(self):
        # При выводе нужно будет расшифровывать данные
        middle = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.last_name} {self.first_name}{middle}"


class Costume(models.Model):
    """Костюмы"""
    STATE_CHOICES = [
        ('Отличное', 'Отличное'),
        ('Хорошее', 'Хорошее'),
        ('Удовлетворительное', 'Удовлетворительное'),
        ('Требует ремонта', 'Требует ремонта'),
        ('Списан', 'Списан'),
    ]
    
    name = models.CharField(
        max_length=50,
        verbose_name="Название костюма"
    )
    inventory_code = models.CharField(
        max_length=14,
        unique=True,
        verbose_name="Инвентарный код",
        help_text="Например, 00000000000001"
    )
    description = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name="Описание"
    )
    count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Количество"
    )
    state = models.CharField(
        max_length=28,
        choices=STATE_CHOICES,
        verbose_name="Состояние"
    )
    note = models.CharField(
        max_length=256,
        blank=True,
        verbose_name="Примечание"
    )
    rent_cost = models.DecimalField(
        decimal_places=2,
        max_digits=8,
        verbose_name="Стоимость аренды за сутки",
        help_text="Может быть указано вплоть до копеек",
        default=500.00
    )
    year = models.PositiveIntegerField(
        verbose_name="Год ввода в эксплуатацию",
        blank=True,
        null=True,
        default=2026
    )
    
    # Foreign Keys
    classification = models.ForeignKey(
        CostumeClassification,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Классификация костюма"
    )
    creative_collective = models.ForeignKey(
        CreativeCollective,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Творческий коллектив"
    )
    size = models.ForeignKey(
        CostumeSize,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Размер"
    )
    hold_place = models.ForeignKey(
        HoldPlace,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Место хранения"
    )
    grant_person = models.ForeignKey(
        GrantPerson,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Ответственное лицо"
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Сезон"
    )
    gender = models.ForeignKey(
        Gender,
        on_delete=models.PROTECT,
        related_name='costumes',
        verbose_name="Пол"
    )
    
    # Many-to-Many relationships через промежуточные таблицы
    colors = models.ManyToManyField(
        Color,
        through='CostumeColor',
        related_name='costumes',
        verbose_name="Цвета"
    )
    materials = models.ManyToManyField(
        Material,
        through='CostumeMaterial',
        related_name='costumes',
        verbose_name="Материалы"
    )

    class Meta:
        db_table = 'costume'
        verbose_name = 'Костюм'
        verbose_name_plural = 'Костюмы'
        ordering = ['inventory_code']
        constraints = [
            CheckConstraint(
                condition=Q(count__gte=0),
                name='count_non_negative'
            )
        ]

    def clean(self):
        validate_inventory_code(self.inventory_code)
        validate_costume_count(self.count)
        validate_costume_cost(self.rent_cost)

    def __str__(self):
        return f"{self.inventory_code} - {self.classification.name}"


class CostumeColor(models.Model):
    """Цвета костюмов (промежуточная таблица)"""
    costume = models.ForeignKey(
        Costume,
        on_delete=models.CASCADE,
        verbose_name="Костюм"
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
        verbose_name="Цвет"
    )

    class Meta:
        db_table = 'costume_color'
        verbose_name = 'Цвет костюма'
        verbose_name_plural = 'Цвета костюмов'
        unique_together = [['costume', 'color']]

    def __str__(self):
        return f"{self.costume.inventory_code} - {self.color.name}"


class CostumeMaterial(models.Model):
    """Материалы костюмов (промежуточная таблица)"""
    costume = models.ForeignKey(
        Costume,
        on_delete=models.CASCADE,
        verbose_name="Костюм"
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        verbose_name="Материал"
    )

    class Meta:
        db_table = 'costume_material'
        verbose_name = 'Материал костюма'
        verbose_name_plural = 'Материалы костюмов'
        unique_together = [['costume', 'material']]

    def __str__(self):
        return f"{self.costume.inventory_code} - {self.material.name}"


class CostumePhoto(models.Model):
    """Фотографии костюмов"""
    photo = models.ImageField(
        upload_to='costumes_photo/%Y/%m/',
        verbose_name="Фотография костюма"
    )
    costume = models.ForeignKey(
        Costume,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Костюм"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата загрузки"
    )

    class Meta:
        db_table = 'costume_photo'
        verbose_name = 'Фотография костюма'
        verbose_name_plural = 'Фотографии костюмов'
        ordering = ['-uploaded_at']

    def clean(self):
        validate_photo_format(self.photo)
        validate_image_size(self.photo)

    def __str__(self):
        return f"Фото {self.costume.inventory_code}"


class Renter(models.Model):
    """Арендаторы"""
    uuid = models.CharField(
        max_length=36,
        verbose_name="UUID"
    )
    last_name = EncryptedCharField(
        max_length=100,
        verbose_name="Фамилия"
    )
    first_name = EncryptedCharField(
        max_length=100,
        verbose_name="Имя"
    )
    middle_name = EncryptedCharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Отчество"
    )
    phone_number = EncryptedCharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Номер телефона"
    )
    email = EncryptedCharField(
        max_length=254,
        blank=True,
        null=True,
        verbose_name="Электронная почта"
    )

    class Meta:
        db_table = 'renter'
        verbose_name = 'Арендатор'
        verbose_name_plural = 'Арендаторы'
        ordering = ['last_name', 'first_name']

    def clean(self):
        validate_phone_number(self.phone_number)

    def __str__(self):
        middle = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.last_name} {self.first_name}{middle}"

class TicketStatus(models.Model):
    STATUS_CHOICES = [
        ('Новая', 'Новая'),
        ('В работе', 'В работе'),
        ('Закрыта', 'Закрыта'),
    ]

    name = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        verbose_name='Название статуса',
        unique=True
    )

    class Meta:
        db_table = 'ticket_status'
        verbose_name = 'Статус заявки поддержки'
        verbose_name_plural = 'Статусы заявок поддержки'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ticket(models.Model):
    theme = models.CharField(
        max_length=256,
        verbose_name='Тема заявки в поддержку',
        null=False,
        blank=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создана'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновленена'
    )

    status = models.ForeignKey(
        TicketStatus,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name='Статус заявки поддеркжи',
    )
    renter = models.ForeignKey(
        Renter,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name='От кого заявка'
    )
    support = models.ForeignKey(
        GrantPerson,
        on_delete=models.CASCADE,
        null=True,
        related_name='tickets',
        verbose_name='Кто работает с заявкой'
    )

    class Meta:
        db_table = 'ticket'
        verbose_name = 'Заявка в поддержку'
        verbose_name_plural = 'Заявки в поддержку'
        ordering = ['status']

    def __str__(self):
        return f'{self.theme}'

class TicketMessages(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='ticket_msgs',
        verbose_name='Заявка в поддержку'
    )
    msg = models.TextField(
        max_length=1024,
        null=False,
        blank=False,
        verbose_name='Сообщение'
    )
    sender_id = models.CharField(
        max_length=36,
        verbose_name='Код отправителя'
    )
    is_read = models.BooleanField(
        verbose_name='Прочитано?',
        default=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Отправлено'
    )

    class Meta:
        db_table = 'ticket_messages'
        verbose_name = 'Сообщение в заявке'
        verbose_name_plural = 'Сообщения в заявке'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.from_msg} - {self.to_msg}'


class MediaTicketMessages(models.Model):
    media = models.ImageField(
        verbose_name='Приложенные изображения в сообщении',
        upload_to='messages_photo/%Y/%m/'
    )
    ticket_message = models.ForeignKey(
        TicketMessages,
        on_delete=models.CASCADE,
        related_name='medias',
        verbose_name='Сообщение'
    )

    class Meta:
        db_table = 'ticket_messages_medias'
        verbose_name = 'Медиа в сообщении'
        verbose_name_plural = 'Медиа в сообщении'

class RequestStatus(models.Model):
    """Статусы заявок"""
    STATUS_CHOICES = [
        ('Новая', 'Новая'),
        ('В обработке', 'В обработке'),
        ('Одобрена', 'Одобрена'),
        ('Выполнена', 'Выполнена'),
        ('Отменена', 'Отменена'),
    ]
    
    name = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        verbose_name="Название статуса",
        unique=True
    )

    class Meta:
        db_table = 'request_status'
        verbose_name = 'Статус заявки'
        verbose_name_plural = 'Статусы заявок'
        ordering = ['name']

    def __str__(self):
        return self.name


class Request(models.Model):
    """Заявки на аренду"""
    date = models.DateField(
        auto_now_add=True,
        verbose_name="Дата заявки"
    )
    time = models.TimeField(
        auto_now_add=True,
        verbose_name="Время заявки"
    )
    renter = models.ForeignKey(
        Renter,
        on_delete=models.PROTECT,
        related_name='requests',
        verbose_name="Арендатор"
    )
    status = models.ForeignKey(
        RequestStatus,
        on_delete=models.PROTECT,
        related_name='requests',
        verbose_name="Статус заявки"
    )
    
    # Many-to-Many с костюмами через промежуточную таблицу
    costumes = models.ManyToManyField(
        Costume,
        through='RequestItem',
        related_name='requests',
        verbose_name="Костюмы"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создана"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлена"
    )

    class Meta:
        db_table = 'request'
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f"Заявка №{self.id} от {self.date}"


class RequestItem(models.Model):
    """Элементы заявки (костюмы в заявке)"""
    costume = models.ForeignKey(
        Costume,
        on_delete=models.PROTECT,
        verbose_name="Костюм"
    )
    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Заявка"
    )
    quantity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Количество"
    )

    class Meta:
        db_table = 'request_item'
        verbose_name = 'Элемент заявки'
        verbose_name_plural = 'Элементы заявок'
        unique_together = [['costume', 'request']]
        constraints = [
            CheckConstraint(
                condition=Q(quantity__gte=1),
                name='quantity_positive'
            )
        ]

    def clean(self):
        validate_request_item_quantity(self.costume, self.quantity)

    def __str__(self):
        return f"{self.costume.inventory_code} x {self.quantity}"


class RentStatus(models.Model):
    """Статусы аренды"""
    STATUS_CHOICES = [
        ('Активна', 'Активна'),
        ('Завершена', 'Завершена'),
        ('Просрочена', 'Просрочена'),
        ('Отменена', 'Отменена'),
        ('В обработке', 'В обработке'),
    ]
    
    name = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        verbose_name="Название статуса",
        unique=True
    )

    class Meta:
        db_table = 'rent_status'
        verbose_name = 'Статус аренды'
        verbose_name_plural = 'Статусы аренды'
        ordering = ['name']

    def __str__(self):
        return self.name

def first_available_date_for_rent():
    now_date = timezone.now().date()
    first_available_date_for_rent = now_date + timedelta(days=14)
    return first_available_date_for_rent

def date_now():
    return timezone.now().date()

def time_now():
    return timezone.now().time()

class Rent(models.Model):
    """Аренда костюмов"""
    date_start = models.DateField(
        default=first_available_date_for_rent,
        verbose_name="Дата начала аренды"
    )
    time_start = models.TimeField(
        default=time_now,
        verbose_name="Время начала аренды"
    )
    date_end = models.DateField(
        verbose_name="Дата окончания аренды"
    )
    time_end = models.TimeField(
        verbose_name="Время окончания аренды"
    )
    
    request = models.OneToOneField(
        Request,
        on_delete=models.PROTECT,
        related_name='rent',
        verbose_name="Заявка"
    )
    status = models.ForeignKey(
        RentStatus,
        on_delete=models.PROTECT,
        related_name='rents',
        verbose_name="Статус аренды"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создана"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлена"
    )

    class Meta:
        db_table = 'rent'
        verbose_name = 'Аренда'
        verbose_name_plural = 'Аренды'
        ordering = ['-created_at']
        constraints = [
            CheckConstraint(
                condition=Q(date_end__gte=models.F('date_start')),
                name='end_date_after_start_date'
            )
        ]

    def clean(self):
        validate_rent_dates(self.date_start, self.time_start, self.date_end, self.time_end)

    def __str__(self):
        return f"Аренда №{self.id} ({self.date_start} - {self.date_end})"