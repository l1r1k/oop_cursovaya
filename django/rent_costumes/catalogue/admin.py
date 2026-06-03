from django.contrib import admin
from django.utils.html import format_html
from django.db import models
from django.forms import TextInput
from .models import (
    MaterialClassification, Material, ColorClassification, Color, CostumeSize,
    HoldPlace, CreativeCollective, CostumeClassification,
    Season, Gender, GrantPerson, Costume, CostumeColor,
    CostumeMaterial, CostumePhoto, Renter, RequestStatus,
    Request, RequestItem, RentStatus, Rent
)
from .encryption import decrypt_field


class BaseEncryptedAdmin(admin.ModelAdmin):
    """
    Базовый класс для моделей с зашифрованными данными
    """
    
    def get_decrypted_value(self, obj, field_name):
        """
        Получает расшифрованное значение поля
        """
        encrypted_value = getattr(obj, field_name, None)
        if encrypted_value:
            try:
                return decrypt_field(encrypted_value)
            except:
                return "Ошибка дешифрования"
        return "-"


@admin.register(MaterialClassification)
class MaterialClassificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'classification']
    list_filter = ['classification']
    search_fields = ['name']
    ordering = ['name']
    autocomplete_fields = ['classification']

@admin.register(ColorClassification)
class ColorClassificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    ordering = ['name']

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'hex_code', 'color_preview']
    list_filter = ['classification']
    search_fields = ['name', 'hex_code']
    ordering = ['name']
    autocomplete_fields = ['classification']
    
    def color_preview(self, obj):
        """
        Отображает цветной квадрат для предварительного просмотра
        """
        if obj.hex_code:
            return format_html(
                '<div style="width: 30px; height: 30px; background-color: {}; border: 1px solid #000;"></div>',
                obj.hex_code
            )
        return "-"
    color_preview.short_description = "Превью"


@admin.register(CostumeSize)
class CostumeSizeAdmin(admin.ModelAdmin):
    list_display = ['id', 'label', 'min_age', 'max_age', 'is_child', 'age_range']
    list_filter = ['is_child']
    search_fields = ['label']
    ordering = ['min_age', 'label']
    
    def age_range(self, obj):
        """
        Отображает диапазон возраста
        """
        return f"{obj.min_age}-{obj.max_age} лет"
    age_range.short_description = "Возрастной диапазон"


@admin.register(HoldPlace)
class HoldPlaceAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'photo_preview', 'costumes_count']
    search_fields = ['name']
    ordering = ['name']
    
    def photo_preview(self, obj):
        """
        Миниатюра фотографии места хранения
        """
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 150px; max-width: 250px;" />',
                obj.photo.url
            )
        return "-"
    photo_preview.short_description = "Фото"
    
    def costumes_count(self, obj):
        """
        Количество костюмов в этом месте
        """
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


@admin.register(CreativeCollective)
class CreativeCollectiveAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'costumes_count']
    search_fields = ['name']
    ordering = ['name']
    
    def costumes_count(self, obj):
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


@admin.register(CostumeClassification)
class CostumeClassificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'parent', 'full_path', 'costumes_count']
    list_filter = ['parent']
    search_fields = ['name']
    ordering = ['parent__name', 'name']
    autocomplete_fields = ['parent']
    
    def full_path(self, obj):
        """
        Полный путь классификации
        """
        if obj.parent:
            return f"{obj.parent.name} > {obj.name}"
        return obj.name
    full_path.short_description = "Путь"
    
    def costumes_count(self, obj):
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'costumes_count']
    ordering = ['name']
    search_fields = ['id', 'name']
    
    def costumes_count(self, obj):
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


@admin.register(Gender)
class GenderAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'costumes_count']
    ordering = ['name']
    search_fields = ['id', 'name']
    
    def costumes_count(self, obj):
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


@admin.register(GrantPerson)
class GrantPersonAdmin(BaseEncryptedAdmin):
    list_display = [
        'id', 
        'last_name', 
        'first_name', 
        'middle_name',
        'phone_number', 
        'email',
        'costumes_count'
    ]
    search_fields = ['first_name', 'last_name']
    ordering = ['last_name', 'first_name']
    formfield_overrides = {
        models.TextField: {'widget': TextInput},
    }
    
    def costumes_count(self, obj):
        return obj.costumes.count()
    costumes_count.short_description = "Костюмов"


class CostumePhotoInline(admin.TabularInline):
    model = CostumePhoto
    extra = 1
    fields = ['photo', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class CostumeColorInline(admin.TabularInline):
    model = CostumeColor
    extra = 1
    autocomplete_fields = ['color']


class CostumeMaterialInline(admin.TabularInline):
    model = CostumeMaterial
    extra = 1
    autocomplete_fields = ['material']


@admin.register(Costume)
class CostumeAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'inventory_code', 
        'classification', 
        'size',
        'available_count', 
        'state',
        'rent_cost',
        'hold_place',
        'grant_person_fio',
        'year',
        'creative_collective',
        'season',
        'gender',
        'photos_count'
    ]
    list_filter = [
        'state', 
        'season', 
        'gender', 
        'creative_collective',
        'classification',
        'size__is_child'
    ]
    search_fields = [
        'name'
        'inventory_code', 
        'description'
    ]
    autocomplete_fields = [
        'classification',
        'creative_collective',
        'size',
        'hold_place',
        'grant_person',
        'season',
        'gender'
    ]
    inlines = [CostumePhotoInline, CostumeColorInline, CostumeMaterialInline]
    readonly_fields = ['photos_count']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name','inventory_code', 'classification', 'description', 'count', 'state', 'rent_cost', 'year')
        }),
        ('Характеристики', {
            'fields': ('size', 'season', 'gender')
        }),
        ('Принадлежность и хранение', {
            'fields': ('creative_collective', 'hold_place', 'grant_person')
        }),
        ('Дополнительно', {
            'fields': ('note',)
        }),
    )

    def available_count(self,obj):
        available = obj.count
        on_rent = 0
        request_items = RequestItem.objects.filter(costume=obj.pk)
        work_statuses = ['Новая', 'В обработке', 'Одобрена']
        for request_item in request_items:
            status = RequestStatus.objects.get(pk=request_item.request.status.pk)
            if status.name in work_statuses:
                on_rent += request_item.quantity
        return f'Доступно - {available} шт. В прокате - {on_rent} шт.'
    available_count.short_description = "Количество"

    def grant_person_fio(self, obj):
        first_name = obj.grant_person.first_name
        last_name = obj.grant_person.last_name
        middle_name = obj.grant_person.middle_name if obj.grant_person.middle_name != 'Отсутствует' else ''

        return f'{last_name} {first_name} {middle_name}'
    grant_person_fio.short_description = 'Подотчетное лицо'
    
    def photos_count(self, obj):
        return obj.photos.count()
    photos_count.short_description = "Фото"


@admin.register(CostumePhoto)
class CostumePhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'costume', 'photo_preview', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['costume__name','costume__inventory_code']
    autocomplete_fields = ['costume']
    readonly_fields = ['uploaded_at', 'photo_preview']
    
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 150px; max-width: 200px;" />',
                obj.photo.url
            )
        return "-"
    photo_preview.short_description = "Превью"


@admin.register(Renter)
class RenterAdmin(BaseEncryptedAdmin):
    list_display = [
        'id',
        'last_name',
        'first_name',
        'middle_name',
        'phone_number',
        'email',
        'requests_count'
    ]
    search_fields = ['first_name', 'last_name']
    ordering = ['last_name', 'first_name']
    formfield_overrides = {
        models.TextField: {'widget': TextInput},
    }
    
    def requests_count(self, obj):
        return obj.requests.count()
    requests_count.short_description = "Заявок"


@admin.register(RequestStatus)
class RequestStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'requests_count']
    ordering = ['name']
    search_fields = ['id', 'name']
    
    def requests_count(self, obj):
        return obj.requests.count()
    requests_count.short_description = "Заявок"


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 1
    autocomplete_fields = ['costume']


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = [
        'display_id',
        'date',
        'time',
        'renter',
        'renter_phone_number',
        'status',
        'items_count',
        'has_rent',
        'created_at'
    ]
    list_filter = ['status', 'date', 'created_at']
    search_fields = ['id', 'renter__last_name', 'renter__first_name']
    autocomplete_fields = ['renter', 'status']
    readonly_fields = ['date', 'time', 'created_at', 'updated_at', 'items_count']
    inlines = [RequestItemInline]
    
    fieldsets = (
        ('Информация о заявке', {
            'fields': ('date', 'time', 'renter', 'status')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def display_id(self, obj):
        return f"Заявка №{obj.id}"
    display_id.short_description = "Номер заявки"

    def renter_phone_number(self, obj):
        return obj.renter.phone_number
    renter_phone_number.short_description = "Номер телефона"
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = "Позиций"
    
    def has_rent(self, obj):
        return hasattr(obj, 'rent')
    has_rent.boolean = True
    has_rent.short_description = "Есть аренда"


@admin.register(RequestItem)
class RequestItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'request', 'costume', 'quantity']
    list_filter = ['request__status', 'request__date']
    search_fields = ['costume__name','costume__inventory_code', 'request__id']
    autocomplete_fields = ['costume', 'request']


@admin.register(RentStatus)
class RentStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'rents_count']
    ordering = ['name']
    search_fields = ['id', 'name']
    
    def rents_count(self, obj):
        return obj.rents.count()
    rents_count.short_description = "Аренд"


@admin.register(Rent)
class RentAdmin(admin.ModelAdmin):
    list_display = [
        'request',
        'date_start',
        'time_start',
        'date_end',
        'time_end',
        'status',
        'is_overdue',
        'duration_days'
    ]
    list_filter = ['status', 'date_start', 'date_end']
    search_fields = ['id', 'request__id', 'request__renter__last_name']
    autocomplete_fields = ['request', 'status']
    readonly_fields = ['date_start', 'time_start', 'created_at', 'updated_at', 'duration_days']
    
    fieldsets = (
        ('Информация об аренде', {
            'fields': ('request', 'status')
        }),
        ('Период аренды', {
            'fields': (
                ('date_start', 'time_start'),
                ('date_end', 'time_end'),
                'duration_days'
            )
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue(self, obj):
        """
        Проверяет, просрочена ли аренда
        """
        from datetime import date
        
        if obj.date_end < date.today():
            return True
        return False
    is_overdue.boolean = True
    is_overdue.short_description = "Просрочена"
    
    def duration_days(self, obj):
        """
        Вычисляет продолжительность аренды в днях
        """
        delta = obj.date_end - obj.date_start
        return f"{delta.days} дней"
    duration_days.short_description = "Длительность"


admin.site.site_header = "Управление костюмами"
admin.site.site_title = "Костюмы - Админ"
admin.site.index_title = "Панель управления"