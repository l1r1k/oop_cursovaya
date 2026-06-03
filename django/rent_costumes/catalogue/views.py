from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count, F
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from datetime import datetime
import json

from .models import (
    Costume, CostumeClassification, CostumeSize, Color,
    Request, RequestItem, RequestStatus, Renter,
    Rent, RentStatus, Ticket, TicketStatus, TicketMessages, MediaTicketMessages,
    GrantPerson,
)
from .encryption import decrypt_field, encrypt_field
from . import identity as identity_service
from . import support_media as support_media_service
from . import support_ticket_rules as ticket_rules


# Pages (Catalogue page, Detail Costume Page, Cart page, Track request status page, Manager page)

def catalog_page(request):
    """Страница каталога костюмов"""
    return render(request, 'costumes/catalog.html')

def costume_detail_page(request, costume_id):
    """Страница подробной информации о костюме"""
    costume = get_object_or_404(Costume, id=costume_id)
    return render(request, 'costumes/costume_detail.html', {
        'costume_id': costume_id
    })

def cart_page(request):
    """Страница корзины"""
    return render(request, 'cart/cart.html')

def track_request_page(request):
    """Страница отслеживания заявки"""
    return render(request, 'requests/track_request.html')

def support_page(request):
    """Страница поддержки"""
    return render(request, 'support/support.html')

@login_required
def manager_page(request):
    """Страница менеджера"""
    return render(request, 'manager/manager.html')

def support_panel_page(request):
    """Панель поддержки для сотрудников"""
    return render(request, 'support/support_panel.html')


# Catalogue API-endpoints

@require_http_methods(["GET"])
def api_catalog_filters(request):
    """
    API: Получение данных для фильтров каталога
    GET /api/catalog/filters/
    """
    # Размеры
    sizes = list(CostumeSize.objects.values('id', 'label', 'min_age', 'max_age', 'is_child').order_by('id'))
    
    # Родительские классификации
    parent_classifications = list(
        CostumeClassification.objects.filter(parent__isnull=True)
        .values('id', 'name').order_by('id')
    )
    
    # Цвета
    colors = list(Color.objects.values('id', 'name', 'hex_code'))
    
    return JsonResponse({
        'sizes': sizes,
        'classifications': parent_classifications,
        'colors': colors
    })


@require_http_methods(["GET"])
def api_catalog_list(request):
    """
    API: Список костюмов с фильтрацией и поиском
    EXAMPLE URL ROUTE: GET /api/catalog/list/?page=1&size=1,2&classification=3&color=4&search=test
    """
    costumes = Costume.objects.select_related(
        'classification',
        'classification__parent',
        'creative_collective',
        'size'
    ).prefetch_related('photos', 'colors').filter(count__gte=0)
    
    # Фильтр по размеру
    size_ids = request.GET.get('size')
    if size_ids:
        size_ids = [int(x) for x in size_ids.split(',')]
        costumes = costumes.filter(size_id__in=size_ids)
    
    # Фильтр по классификации (родительской классификации)
    classification_ids = request.GET.get('classification')
    if classification_ids:
        classification_ids = [int(x) for x in classification_ids.split(',')]
        costumes = costumes.filter(
            Q(classification_id__in=classification_ids) |
            Q(classification__parent_id__in=classification_ids)
        )
    
    # Фильтр по цвету
    color_ids = request.GET.get('color')
    if color_ids:
        color_ids = [int(x) for x in color_ids.split(',')]
        costumes = costumes.filter(colors__id__in=color_ids).distinct()
    
    # Поиск
    search = request.GET.get('search', '').strip()
    if search:
        costumes = costumes.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(classification__name__icontains=search)
        )

    
    # Пагинация
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 12))
    paginator = Paginator(costumes, per_page)
    page_obj = paginator.get_page(page)
    
    # Формирование данных
    items = []
    for costume in page_obj:
        # Первое фото или заглушка
        first_photo = costume.photos.first()
        photo_url = first_photo.photo.url if first_photo else None
        
        # Классификация с родителем
        classification_full = costume.classification.name
        if costume.classification.parent:
            classification_full = f"{costume.classification.parent.name} > {costume.classification.name}"
        
        items.append({
            'id': costume.id,
            'name': costume.name,
            'inventory_code': costume.inventory_code,
            'description': costume.description[:100] if costume.description else '',
            'classification': classification_full,
            'creative_collective': costume.creative_collective.name,
            'rent_cost': costume.rent_cost,
            'photo': photo_url,
            'count': costume.count,
            'size': costume.size.label,
            'colors': [{'name': c.name, 'hex': c.hex_code} for c in costume.colors.all()[:3]]
        })
    
    return JsonResponse({
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginator.count,
            'pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_prev': page_obj.has_previous()
        }
    })


# Costume details API-endpoints

@require_http_methods(["GET"])
def api_costume_detail(request, costume_id):
    """
    API: Подробная информация о костюме
    URL ROUTE: GET /api/costume/<id>/
    """
    costume = get_object_or_404(
        Costume.objects.select_related(
            'classification', 'classification__parent',
            'creative_collective', 'size', 'season', 'gender',
            'hold_place'
        ).prefetch_related('photos', 'colors', 'materials'),
        id=costume_id
    )
    
    # Классификация
    classification_full = costume.classification.name
    if costume.classification.parent:
        classification_full = f"{costume.classification.parent.name} > {costume.classification.name}"
    
    # Фотографии
    photos = [{'id': p.id, 'url': p.photo.url} for p in costume.photos.all()]
    
    # Цвета
    colors = [{'name': c.name, 'hex': c.hex_code} for c in costume.colors.all()]
    
    # Материалы
    materials = [{'name': m.name} for m in costume.materials.all()]
    
    data = {
        'id': costume.id,
        'name': costume.name,
        'inventory_code': costume.inventory_code,
        'description': costume.description,
        'classification': classification_full,
        'creative_collective': costume.creative_collective.name,
        'size': {
            'label': costume.size.label,
            'min_age': costume.size.min_age,
            'max_age': costume.size.max_age,
            'is_child': costume.size.is_child
        },
        'rent_cost': costume.rent_cost,
        'season': costume.season.name,
        'gender': costume.gender.name,
        'count': costume.count,
        'state': costume.state,
        'photos': photos,
        'colors': colors,
        'materials': materials,
        'note': costume.note if costume.note else ''
    }
    
    return JsonResponse(data)


# Cart API-endpoints

@require_http_methods(["POST"])
@csrf_exempt
def api_cart_add(request):
    """
    API: Добавление костюма в корзину
    URL ROUTE: POST /api/cart/add/
    EXAMPLE BODY: {"costume_id": 1, "quantity": 2}
    """
    try:
        data = json.loads(request.body)
        costume_id = data.get('costume_id')
        quantity = data.get('quantity', 1)
        
        costume = get_object_or_404(Costume, id=costume_id)
        
        if quantity > costume.count:
            return JsonResponse({
                'success': False,
                'error': f'Доступно только {costume.count} шт.'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': 'Добавлено в корзину'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def api_cart_update(request):
    """
    API: Обновление количества в корзине
    URL ROUTE: POST /api/cart/update/
    EXAMPLE BODY: {"costume_id": 1, "quantity": 3}
    """
    try:
        data = json.loads(request.body)
        costume_id = data.get('costume_id')
        quantity = data.get('quantity', 1)
        
        costume = get_object_or_404(Costume, id=costume_id)
        
        if quantity > costume.count:
            return JsonResponse({
                'success': False,
                'error': f'Доступно только {costume.count} шт.'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': 'Количество обновлено'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=400)


# Send request API-endpoints

@require_http_methods(["POST"])
@csrf_exempt
@transaction.atomic
def api_create_request(request):
    """
    API: Создание заявки на аренду
    URL ROUTE: POST /api/request/create/
    EXAMPLE BODY: {
        "renter": {
            "uuid": "73f817a0-d7a3-49de-8c15-a6ebb3a7bcc0",
            "first_name": "Иван",
            "last_name": "Иванов",
            "middle_name": "Петрович",
            "phone_number": "+79991234567",
            "email": "ivan@example.com"
        },
        "items": [
            {"costume_id": 1, "quantity": 2},
            {"costume_id": 2, "quantity": 1}
        ]
    }
    """
    try:
        data = json.loads(request.body)
        renter_data = data.get('renter', {})
        items_data = data.get('items', [])
        
        if not renter_data or not items_data:
            return JsonResponse({
                'success': False,
                'error': 'Необходимо указать данные арендатора и состав заявки'
            }, status=400)
        
        # Проверка существует ли пользователь
        renter = None
        phone_number = renter_data.get('phone_number')
        email = renter_data.get('email')
        
        # Поиск существующего арендатора по email или телефону
        if email or phone_number:
            all_renters = Renter.objects.all()
            
            for existing_renter in all_renters:
                if email and existing_renter.email:
                    try:
                        if existing_renter.email and existing_renter.email.lower() == email.lower():
                            renter = existing_renter
                            break
                    except:
                        pass
                
                if not renter and phone_number and existing_renter.phone_number:
                    try:
                        # Нормализация номера телефона для проверки (все кроме цифр для сравнения)
                        if existing_renter.phone_number:
                            normalized_existing = ''.join(filter(str.isdigit, existing_renter.phone_number))
                            normalized_new = ''.join(filter(str.isdigit, phone_number))
                            if normalized_existing == normalized_new:
                                renter = existing_renter
                                break
                    except:
                        pass
        
        # Если арендатор не найден, создаем нового
        if not renter:
            renter = Renter.objects.create(
                uuid=renter_data.get('uuid'),
                first_name=renter_data.get('first_name', ''),
                last_name=renter_data.get('last_name', ''),
                middle_name=renter_data.get('middle_name') if renter_data.get('middle_name') else None,
                phone_number=phone_number if phone_number else None,
                email=email if email else None
            )
        
        # Создаем заявку
        status_new = RequestStatus.objects.get_or_create(name='Новая')[0]
        rental_request = Request.objects.create(
            renter=renter,
            status=status_new
        )
        
        # Добавляем элементы заявки
        for item_data in items_data:
            costume = get_object_or_404(Costume, id=item_data['costume_id'])
            quantity = item_data.get('quantity', 1)
            
            # Проверка доступности
            if quantity > costume.count:
                rental_request.delete()
                return JsonResponse({
                    'success': False,
                    'error': f'Костюм {costume.inventory_code}: доступно только {costume.count} шт.'
                }, status=400)
            
            RequestItem.objects.create(
                request=rental_request,
                costume=costume,
                quantity=quantity
            )

        reserve_costumes(rental_request)
        
        if renter_data.get('email'):
            send_request_email(rental_request, renter.email)
        
        return JsonResponse({
            'success': True,
            'request_id': rental_request.id,
            'message': f'Заявка #{rental_request.id} успешно создана'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=500)


def send_request_email(rental_request, email):
    """Отправка email с подтверждением заявки"""
    try:
        if not '@' in email:
            email = decrypt_field(email)
        
        items = rental_request.items.select_related('costume').prefetch_related('costume__photos')

        full_name = f'{rental_request.renter.first_name} {rental_request.renter.last_name} {rental_request.renter.middle_name if rental_request.renter.middle_name else ""}'
        
        html_message = render_to_string('email/email_request_confirmation.html', {
            'header_text': 'Заявка успешно создана!',
            'request_id': rental_request.id,
            'items': items,
            'track_url': f"{settings.SITE_URL}/track",
            'site_url': settings.SITE_URL,
            'ordering': True,
            'rent': None,
            'final_cost': None,
            'full_name': full_name
        })
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Заявка #{rental_request.id} успешно создана',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as e:
        print(f"Error sending email: {e}")


# Track request status API-endpoints

@require_http_methods(["GET"])
def api_track_request(request, request_id):
    """
    API: Отслеживание заявки
    URL ROUTE: GET /api/request/<id>/track/
    """
    try:
        rental_request = get_object_or_404(
            Request.objects.select_related('status', 'renter')
            .prefetch_related('items__costume__photos'),
            id=request_id
        )
        
        items = []
        for item in rental_request.items.all():
            photo = item.costume.photos.first()
            items.append({
                'costume_id': item.costume.id,
                'name': item.costume.name,
                'inventory_code': item.costume.inventory_code,
                'description': item.costume.description,
                'quantity': item.quantity,
                'cost': item.costume.rent_cost,
                'photo': photo.photo.url if photo else None
            })
        
        data = {
            'id': rental_request.id,
            'date': rental_request.date.strftime('%d.%m.%Y'),
            'time': rental_request.time.strftime('%H:%M'),
            'status': rental_request.status.name,
            'items': items
        }
        
        if hasattr(rental_request, 'rent'):
            rent = rental_request.rent
            delta = rent.date_end - rent.date_start
            total_cost = 0

            for item in rental_request.items.all():
                total_cost += item.costume.rent_cost * item.quantity * delta.days

            data['rent'] = {
                'date_start': rent.date_start.strftime('%d.%m.%Y'),
                'date_end': rent.date_end.strftime('%d.%m.%Y'),
                'status': rent.status.name,
                'delta': delta.days,
                'total_cost': total_cost
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': 'Заявка не найдена'
        }, status=404)


# Manager API-endpoints

def reserve_costumes(request_obj):
    """
    Резерв костюмов. Вызывается при оформлении заявки клиентом
    """
    with transaction.atomic():
        for item in request_obj.items.select_related('costume'):
            costume = item.costume
            
            costume = Costume.objects.select_for_update().get(id=costume.id)
            
            if costume.count < item.quantity:
                raise ValueError(f'Недостаточно костюмов: {costume.inventory_code}')
            
            costume.count = F('count') - item.quantity
            costume.save()
            costume.refresh_from_db()


def release_costumes(request_obj):
    """
    Возврат костюмы. Вызывается при завершении или отмене аренды/заявки
    """
    with transaction.atomic():
        for item in request_obj.items.select_related('costume'):
            costume = item.costume
            
            costume = Costume.objects.select_for_update().get(id=costume.id)
            
            costume.count = F('count') + item.quantity
            costume.save()
            costume.refresh_from_db()


def should_release_costumes_for_request(rental_request, old_status_name, new_status_name):
    """
    Нужно ли освобождать костюмы при изменении статуса заявки
    """
    released_statuses = ['Отклонена', 'Отменена', 'Выполнена']
    
    if new_status_name not in released_statuses:
        return False
    
    if old_status_name in released_statuses:
        return False
    
    try:
        rent = Rent.objects.get(request=rental_request)
        
        rent_released_statuses = ['Завершена', 'Отменена']
        if rent.status.name in rent_released_statuses:
            return False
        else:
            return False
            
    except Rent.DoesNotExist:
        pass
    
    return True

def should_release_costumes_for_rent(rent, old_status_name, new_status_name):
    """
    Нужно ли освобождать костюмы при изменении статуса аренды
    """
    released_statuses = ['Завершена', 'Отменена']
    
    if new_status_name not in released_statuses:
        return False
    
    if old_status_name in released_statuses:
        return False
    
    return True

@login_required
@require_http_methods(["GET"])
def api_manager_stats(request):
    """
    API: Статистика для менеджера
    URL ROUTE: GET /api/manager/stats/
    """
    requests_stats = Request.objects.values('status__name').annotate(
        count=Count('id')
    )
    
    rents_stats = Rent.objects.values('status__name').annotate(
        count=Count('id')
    )
    
    return JsonResponse({
        'requests': {
            'total': Request.objects.count(),
            'by_status': list(requests_stats)
        },
        'rents': {
            'total': Rent.objects.count(),
            'by_status': list(rents_stats)
        }
    })

@login_required
@require_http_methods(["GET"])
def api_manager_requests_items(request, id):
    """
    API: Подробный состав костюмов в заявке
    URL ROUTE: GET api/manager/requests/<int:id>/items/
    """
    rental_request = get_object_or_404(Request, id=id)
    request_items = rental_request.items.select_related('costume').prefetch_related('costume__photos')

    items = []
    final_cost_per_day = 0
    for req_item in request_items:
        req_item_info = {
            'name': req_item.costume.name,
            'quantity': req_item.quantity,
            'photo': req_item.costume.photos.first().photo.url or '',
            'rent_cost': req_item.costume.rent_cost
        }

        final_cost_per_day += req_item_info['rent_cost'] * req_item_info['quantity']

        items.append({
            'item': req_item_info,
        })

    return JsonResponse({
        'items': items,
        'final_cost_per_day': final_cost_per_day,
    })

@login_required
@require_http_methods(["GET"])
def api_manager_requests(request):
    """
    API: Список заявок для менеджера с информацией об арендаторе
    URL ROUTE: GET /api/manager/requests/?status=1
    """
    requests_qs = Request.objects.select_related(
        'renter', 'status'
    ).prefetch_related('items')
    
    status_id = request.GET.get('status')
    if status_id:
        requests_qs = requests_qs.filter(status_id=status_id)
    
    requests_qs = requests_qs.order_by('-created_at')
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    paginator = Paginator(requests_qs, per_page)
    page_obj = paginator.get_page(page)
    
    items = []
    for req in page_obj:
        renter_info = {
            'id': req.renter.id,
            'first_name': req.renter.first_name or '',
            'last_name': req.renter.last_name or '',
            'middle_name': req.renter.middle_name or '',
            'phone_number': req.renter.phone_number or '',
            'email': req.renter.email or ''
        }
        
        items.append({
            'id': req.id,
            'date': req.date.strftime('%d.%m.%Y'),
            'time': req.time.strftime('%H:%M'),
            'status': {
                'id': req.status.id,
                'name': req.status.name
            },
            'items_count': req.items.count(),
            'has_rent': hasattr(req, 'rent'),
            'renter': renter_info
        })
    
    return JsonResponse({
        'items': items,
        'pagination': {
            'page': page,
            'total': paginator.count,
            'pages': paginator.num_pages
        }
    })


@login_required
@require_http_methods(["GET"])
def api_manager_rents(request):
    """
    API: Список аренд для менеджера с информацией об арендаторе
    URL ROUTE: GET /api/manager/rents/?status=1
    """
    rents_qs = Rent.objects.select_related(
        'request', 'request__renter', 'status'
    )
    
    status_id = request.GET.get('status')
    if status_id:
        rents_qs = rents_qs.filter(status_id=status_id)
    
    rents_qs = rents_qs.order_by('-created_at')
    
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    paginator = Paginator(rents_qs, per_page)
    page_obj = paginator.get_page(page)
    
    items = []
    for rent in page_obj:
        renter = rent.request.renter
        renter_info = {
            'id': renter.id,
            'first_name': renter.first_name or '',
            'last_name': renter.last_name or '',
            'middle_name': renter.middle_name or '',
            'phone_number': renter.phone_number or '',
            'email': renter.email or ''
        }
        
        items.append({
            'id': rent.id,
            'request_id': rent.request.id,
            'date_start': rent.date_start.strftime('%d.%m.%Y'),
            'date_end': rent.date_end.strftime('%d.%m.%Y'),
            'status': {
                'id': rent.status.id,
                'name': rent.status.name
            },
            'renter': renter_info
        })
    
    return JsonResponse({
        'items': items,
        'pagination': {
            'page': page,
            'total': paginator.count,
            'pages': paginator.num_pages
        }
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_manager_update_request_status(request, request_id):
    """
    API: Изменение статуса заявки
    URL ROUTE: POST /api/manager/request/<id>/status/
    EXAMPLE BODY: {"status_id": 2}
    """
    try:
        data = json.loads(request.body)
        status_id = data.get('status_id')
        
        rental_request = get_object_or_404(Request, id=request_id)
        new_status = get_object_or_404(RequestStatus, id=status_id)
        
        old_status_name = rental_request.status.name
        new_status_name = new_status.name
        
        # Проверка на необходимость возвращать количество костюмов
        should_release = should_release_costumes_for_request(
            rental_request, 
            old_status_name, 
            new_status_name
        )
        
        if should_release:
            release_costumes(rental_request)
        
        rental_request.status = new_status
        rental_request.save()
        
        # Отправляем email при отмене/отклонении
        release_statuses = ['Отклонена', 'Отменена']
        if new_status_name in release_statuses and old_status_name not in release_statuses:
            full_name = f'{rental_request.renter.first_name} {rental_request.renter.last_name} {rental_request.renter.middle_name if rental_request.renter.middle_name else ""}'
            
            items = rental_request.items.select_related('costume').prefetch_related('costume__photos')
            
            html_message = render_to_string('email/email_request_cancel.html', {
                'request_id': rental_request.id,
                'items': items,
                'catalog_url': f"{settings.SITE_URL}/",
                'site_url': settings.SITE_URL,
                'full_name': full_name
            })
            
            plain_message = strip_tags(html_message)
            
            renter_email = rental_request.renter.email
            if renter_email:
                send_mail(
                    subject=f'Заявка #{rental_request.id} отменена!',
                    message=plain_message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[renter_email],
                    html_message=html_message,
                    fail_silently=False,
                )
        
        return JsonResponse({
            'success': True,
            'message': f'Статус изменен на "{new_status_name}"',
            'costumes_released': should_release
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_manager_update_rent_status(request, rent_id):
    """
    API: Изменение статуса аренды
    URL ROUTE: POST /api/manager/rent/<id>/status/
    EXAMPLE BODY: {"status_id": 2}
    """
    try:
        data = json.loads(request.body)
        status_id = data.get('status_id')
        
        rent = get_object_or_404(Rent, id=rent_id)
        new_status = get_object_or_404(RentStatus, id=status_id)
        rental_request = rent.request
        
        old_status_name = rent.status.name
        new_status_name = new_status.name
        
        # Проверка на необходимость возвращать количество костюмов
        should_release = should_release_costumes_for_rent(
            rent,
            old_status_name,
            new_status_name
        )
        
        if should_release:
            release_costumes(rental_request)
        
        rent.status = new_status
        rent.save()
        
        # Обновляем статус заявки в зависимости от статуса аренды
        if new_status_name == 'Отменена':
            request_final_statuses = ['Выполнена', 'Отменена']
            if rental_request.status.name not in request_final_statuses:
                canceled_status = RequestStatus.objects.get_or_create(name='Отменена')[0]
                rental_request.status = canceled_status
                rental_request.save()
            
            full_name = f'{rental_request.renter.first_name} {rental_request.renter.last_name} {rental_request.renter.middle_name if rental_request.renter.middle_name else ""}'
            
            items = rental_request.items.select_related('costume').prefetch_related('costume__photos')
            
            html_message = render_to_string('email/email_request_cancel.html', {
                'request_id': rental_request.id,
                'items': items,
                'catalog_url': f"{settings.SITE_URL}/",
                'site_url': settings.SITE_URL,
                'full_name': full_name
            })
            
            plain_message = strip_tags(html_message)
            
            renter_email = rental_request.renter.email
            if renter_email:
                send_mail(
                    subject=f'Заявка #{rental_request.id} отменена!',
                    message=plain_message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[renter_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
        elif new_status_name == 'Завершена':
            completed_status = RequestStatus.objects.get_or_create(name='Выполнена')[0]
            rental_request.status = completed_status
            rental_request.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Статус изменен на "{new_status_name}"',
            'costumes_released': should_release
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=400)



@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_manager_create_rent(request, request_id):
    """
    API: Создание аренды на основе заявки
    URL ROUTE: POST /api/manager/request/<id>/create-rent/
    EXAMPLE BODY: {
        "date_start": "2024-03-20",
        "time_start": "10:00",
        "date_end": "2024-03-25",
        "time_end": "18:00"
    }
    """
    try:
        data = json.loads(request.body)
        rental_request = get_object_or_404(Request, id=request_id)
        
        if rental_request.status.name != 'Одобрена':
            return JsonResponse({
                'success': False,
                'error': 'Заявка должна быть одобрена'
            }, status=400)
        
        if hasattr(rental_request, 'rent'):
            return JsonResponse({
                'success': False,
                'error': 'Аренда уже создана для этой заявки'
            }, status=400)
        
        date_start = datetime.strptime(data['date_start'], '%Y-%m-%d').date()
        time_start = datetime.strptime(data['time_start'], '%H:%M').time()
        date_end = datetime.strptime(data['date_end'], '%Y-%m-%d').date()
        time_end = datetime.strptime(data['time_end'], '%H:%M').time()
        
        status = RentStatus.objects.get_or_create(name='В обработке')[0]
        
        rent = Rent.objects.create(
            request=rental_request,
            status=status,
            date_start=date_start,
            time_start=time_start,
            date_end=date_end,
            time_end=time_end
        )

        completed_status = RequestStatus.objects.get_or_create(name='Выполнена')[0]
        rental_request.status = completed_status
        rental_request.save()

        items = rental_request.items.select_related('costume').prefetch_related('costume__photos')

        delta_rent_days = date_end - date_start
        rent_days = delta_rent_days.days
        final_cost = 0

        for item in items:
            final_cost += item.costume.rent_cost * item.quantity * rent_days

        full_name = f'{rental_request.renter.first_name} {rental_request.renter.last_name} {rental_request.renter.middle_name if rental_request.renter.middle_name else ""}'

        html_message = render_to_string('email/email_request_confirmation.html', {
            'header_text': 'Заявка успешно принята!',
            'request_id': rental_request.id,
            'items': items,
            'track_url': f"{settings.SITE_URL}/track",
            'site_url': settings.SITE_URL,
            'ordering': False,
            'rent': rent,
            'final_cost': final_cost,
            'full_name': full_name
        })
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Заявка #{rental_request.id} успешно принята!',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[rental_request.renter.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return JsonResponse({
            'success': True,
            'rent_id': rent.id,
            'message': 'Аренда успешно создана'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=400)


@login_required
@require_http_methods(["GET"])
def api_manager_statuses(request):
    """
    API: Получение списка статусов
    URL ROUTE: GET /api/manager/statuses/
    """
    request_statuses = list(RequestStatus.objects.values('id', 'name'))
    rent_statuses = list(RentStatus.objects.values('id', 'name'))
    
    return JsonResponse({
        'request_statuses': request_statuses,
        'rent_statuses': rent_statuses
    })

@require_http_methods(["GET"])
def api_costume_availability(request, costume_id):
    """
    API: Проверка доступности костюма. Возвращает реальное количество доступных костюмов (с учетом резервов)
    URL ROUTE: GET /api/costume/<id>/availability/
    """
    try:
        costume = get_object_or_404(Costume, id=costume_id)
        
        return JsonResponse({
            'costume_id': costume.id,
            'inventory_code': costume.inventory_code,
            'total_count': costume.count,
            'is_available': costume.count > 0
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'
        }, status=404)

def _is_grant_person_uuid(uuid_value: str) -> bool:
    """
    Проверяет наличие ответственного лица с полученным UUID
    """
    return bool(uuid_value) and GrantPerson.objects.filter(uuid=uuid_value).exists()


def _is_renter_uuid(uuid_value: str) -> bool:
    """
    Проверяет наличие арендатора с полученным UUID
    """
    return bool(uuid_value) and Renter.objects.filter(uuid=uuid_value).exists()


def _can_access_ticket(ticket: Ticket, renter_uuid: str | None, grant_person_uuid: str | None) -> bool:
    """
    Проверяет доступ к обращению в поддержку
    """
    if grant_person_uuid and _is_grant_person_uuid(grant_person_uuid):
        return True
    if renter_uuid and ticket.renter.uuid == renter_uuid:
        return True
    return False


def _get_access_uuids(request):
    """
    Возвращает UUID из запроса
    """
    renter_uuid = request.GET.get('renter_uuid') or request.headers.get('X-Renter-UUID')
    grant_person_uuid = request.GET.get('grant_person_uuid') or request.headers.get('X-Grant-Person-UUID')
    return renter_uuid, grant_person_uuid


@require_http_methods(['POST'])
@csrf_exempt
def api_support_ticket_create(request):
    """
    API: Создание заявки в поддержку.
    URL ROUTE: POST /api/support/ticket/create/
    JSON или multipart: renter_uuid, theme, body, media[] (до 5 изображений).
    """
    try:
        media_files = []

        if request.content_type.startswith('multipart/'):
            renter_uuid = (request.POST.get('renter_uuid') or '').strip()
            theme = (request.POST.get('theme') or '').strip()
            body = (request.POST.get('body') or '').strip()
            media_files = request.FILES.getlist('media')
        else:
            data = json.loads(request.body or '{}')
            renter_data = data.get('renter', {})
            ticket_data = data.get('ticket', {})
            renter_uuid = (renter_data.get('uuid') or data.get('renter_uuid') or '').strip()
            theme = (ticket_data.get('theme') or data.get('theme') or '').strip()
            body = (ticket_data.get('body') or data.get('body') or '').strip()

        if not renter_uuid or not theme:
            return JsonResponse({'error': 'Укажите renter_uuid и theme'}, status=400)

        if not body and not media_files:
            return JsonResponse({'error': 'Укажите текст обращения или прикрепите изображения'}, status=400)

        renter = Renter.objects.filter(uuid=renter_uuid).first()
        if not renter:
            return JsonResponse({'error': 'Арендатор не найден'}, status=404)

        if ticket_rules.get_renter_open_ticket(renter_uuid):
            return JsonResponse({
                'error': 'У вас уже есть открытая заявка. Закройте её, чтобы создать новую.',
            }, status=400)

        status_new = TicketStatus.objects.get_or_create(name='Новая')[0]
        ticket = Ticket.objects.create(
            theme=theme,
            status=status_new,
            renter=renter,
        )

        ticket_message = TicketMessages.objects.create(
            ticket=ticket,
            msg=body,
            sender_id=renter.uuid,
        )
        support_media_service.save_message_media_files(ticket_message, media_files)

        msg_payload = support_media_service.serialize_ticket_message(ticket_message, request)

        return JsonResponse({
            'success': True,
            'message': f'Обращение #{ticket.pk} успешно создано!',
            'ticket': {
                'ticket_id': ticket.pk,
                'theme': ticket.theme,
                'renter_uuid': renter.uuid,
            },
            'msg': msg_payload,
        })
    except ValidationError as e:
        return JsonResponse({'error': e.messages[0] if e.messages else str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)
    
@require_http_methods(['POST'])
@csrf_exempt
def api_support_ticket_close(request, ticket_id):
    """
    API: Закрытие обращения в поддержку
    URL ROUTE: POST /api/support/ticket/<int:ticket_id>/close/
    """
    try:
        data = json.loads(request.body or '{}')
        renter_uuid = (data.get('renter_uuid') or '').strip()
        grant_person_uuid = (data.get('grant_person_uuid') or '').strip()

        if not renter_uuid and not grant_person_uuid:
            return JsonResponse({'error': 'Укажите renter_uuid или grant_person_uuid'}, status=400)

        if renter_uuid and grant_person_uuid:
            return JsonResponse({'error': 'Укажите только один идентификатор'}, status=400)

        if renter_uuid and not _is_renter_uuid(renter_uuid):
            return JsonResponse({'error': 'Недопустимый UUID арендатора'}, status=403)

        if grant_person_uuid and not _is_grant_person_uuid(grant_person_uuid):
            return JsonResponse({'error': 'Недопустимый UUID сотрудника поддержки'}, status=403)

        ticket = get_object_or_404(
            Ticket.objects.select_related('renter', 'support', 'status'),
            id=ticket_id,
        )

        permission = ticket_rules.evaluate_close_permission(
            ticket,
            renter_uuid or None,
            grant_person_uuid or None,
        )
        if not permission['can_close']:
            return JsonResponse({'error': permission['close_hint']}, status=400)

        ticket.status = ticket_rules.get_closed_status()
        if grant_person_uuid and not ticket.support_id:
            grant_person = GrantPerson.objects.filter(uuid=grant_person_uuid).first()
            if grant_person:
                ticket.support = grant_person
        ticket.save()

        return JsonResponse({
            'success': True,
            'message': f'Обращение #{ticket.pk} успешно закрыто!',
        })
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)

def get_ticket_last_message(ticket_id: int, request=None):
    """
    Возвращает последнее сообщение в обращении
    """
    ticket_last_message = (
        TicketMessages.objects.filter(ticket_id=ticket_id)
        .prefetch_related('medias')
        .order_by('-created_at')
        .first()
    )
    if not ticket_last_message:
        return None

    payload = support_media_service.serialize_ticket_message(ticket_last_message, request)
    payload['msg'] = support_media_service.message_preview_text(ticket_last_message)
    return payload

@require_http_methods(['GET'])
def api_support_tickets(request):
    """
    API: Возвращает все обращения в тех. поддержку
    URL ROUTE: GET /api/support/tickets/
    """
    renter_uuid, grant_person_uuid = _get_access_uuids(request)

    if renter_uuid:
        if not _is_renter_uuid(renter_uuid):
            return JsonResponse({'error': 'Недопустимый UUID арендатора'}, status=403)
        tickets = Ticket.objects.filter(renter__uuid=renter_uuid)
    elif grant_person_uuid:
        if not _is_grant_person_uuid(grant_person_uuid):
            return JsonResponse({'error': 'Недопустимый UUID сотрудника поддержки'}, status=403)
        tickets = Ticket.objects.select_related('renter', 'support', 'status').all()
    else:
        return JsonResponse({'error': 'Укажите renter_uuid или grant_person_uuid'}, status=400)

    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 12))
    paginator = Paginator(tickets, per_page)
    page_obj = paginator.get_page(page)

    items = []

    open_ticket_id = None
    if renter_uuid:
        open_ticket = ticket_rules.get_renter_open_ticket(renter_uuid)
        if open_ticket:
            open_ticket_id = open_ticket.pk

    for ticket in page_obj:
        support_uuid = ticket.support.uuid if ticket.support else None
        close_info = ticket_rules.evaluate_close_permission(
            ticket,
            renter_uuid or None,
            grant_person_uuid or None,
        )
        items.append({
            'ticket_id': ticket.pk,
            'last_msg': get_ticket_last_message(ticket.pk, request),
            'status': ticket.status.name,
            'renter': f'{ticket.renter.last_name} {ticket.renter.first_name} {ticket.renter.middle_name or ""}'.strip(),
            'renter_uuid': ticket.renter.uuid,
            'support_uuid': support_uuid,
            'theme': ticket.theme,
            'created_at': ticket.created_at,
            'is_closed': close_info['is_closed'],
            'can_close': close_info['can_close'],
            'close_hint': close_info['close_hint'],
        })

    return JsonResponse({
        'items': items,
        'has_open_ticket': open_ticket_id is not None,
        'open_ticket_id': open_ticket_id,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginator.count,
            'pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_prev': page_obj.has_previous()
        }
    })

@require_http_methods(['GET'])
def api_support_ticket_ticket_messages(request, ticket_id: int):
    """
    API: Возвращает сообщения в обращении тех. поддержке
    URL ROUTE: GET /api/support/ticket/<int:ticket_id>/ticket-messages/
    """
    renter_uuid, grant_person_uuid = _get_access_uuids(request)
    ticket = get_object_or_404(Ticket.objects.select_related('renter', 'support'), id=ticket_id)

    if not _can_access_ticket(ticket, renter_uuid, grant_person_uuid):
        return JsonResponse({'error': 'Нет доступа к заявке'}, status=403)

    ticket_messages = (
        TicketMessages.objects.filter(ticket_id=ticket_id)
        .prefetch_related('medias')
        .order_by('created_at')
    )
    items = [
        support_media_service.serialize_ticket_message(ticket_message, request)
        for ticket_message in ticket_messages
    ]

    support_uuid = ticket.support.uuid if ticket.support else None
    close_info = ticket_rules.evaluate_close_permission(
        ticket,
        renter_uuid or None,
        grant_person_uuid or None,
    )
    return JsonResponse({
        'msgs': items,
        'renter': {
            'uuid': ticket.renter.uuid,
            'first_name': ticket.renter.first_name,
            'last_name': ticket.renter.last_name,
            'middle_name': ticket.renter.middle_name,
        },
        'ticket': {
            'ticket_id': ticket_id,
            'theme': ticket.theme,
            'status': ticket.status.name,
            'support_uuid': support_uuid,
            'created_at': ticket.created_at,
            'is_closed': close_info['is_closed'],
            'can_close': close_info['can_close'],
            'close_hint': close_info['close_hint'],
        }
    })


@require_http_methods(['GET'])
def api_support_ticket_last_message(request, ticket_id: int):
    """
    API: Возвращает последнее сообщение в обращении в тех. поддержку
    URL ROUTE: GET /api/support/ticket/<int:ticket_id>/last-message/
    """
    try:
        last_message = get_ticket_last_message(ticket_id)
        if not last_message:
            raise Http404('Нет сообщений в заявке!')
        return JsonResponse({
            'msg': last_message
        })

    except Exception as e:
        return JsonResponse({
            'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже',
        }, status=404)

@require_http_methods(['GET'])
def api_renter_exist(request, renter_uuid: str):
    """
    API: Возвращает данные по арендатору
    URL ROUTE: GET /api/support/ticket/message/create/
    """
    renter = Renter.objects.filter(uuid=renter_uuid).first()
    if not renter:
        return JsonResponse({'error': 'Арендатор не найден'}, status=404)

    return JsonResponse({
        'uuid': renter.uuid,
        'exists': True,
        'first_name': renter.first_name,
        'last_name': renter.last_name,
        'middle_name': renter.middle_name,
        'phone_number': renter.phone_number,
        'email': identity_service.get_plain_email(renter.email) or '',
    })


@require_http_methods(['GET'])
def api_identity_renter_check(request, renter_uuid: str):
    """
    API: Проверка наличия арендатора с полученным UUID в системе
    URL ROUTE: GET /api/renter/<str:renter_uuid>/
    """
    exists = Renter.objects.filter(uuid=renter_uuid).exists()
    return JsonResponse({'exists': exists, 'uuid': renter_uuid if exists else None})


@require_http_methods(['GET'])
def api_identity_grant_person_check(request, grant_person_uuid: str):
    """
    API: Проверка наличия ответственного лица с полученным UUID в системе
    URL ROUTE: GET /api/identity/grant-person/<str:grant_person_uuid>/check/
    """
    exists = GrantPerson.objects.filter(uuid=grant_person_uuid).exists()
    return JsonResponse({'exists': exists, 'uuid': grant_person_uuid if exists else None})


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_renter_request_code(request):
    """
    API: Отправка проверочного кода на электронную почту для верификации арендатора
    URL ROUTE: POST api/identity/renter/request-code/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        if not identity_service.EMAIL_RE.match(email):
            return JsonResponse({'error': 'Укажите корректный email'}, status=400)

        renter = identity_service.find_renter_by_email(email)
        if not renter:
            return JsonResponse({'found': False})

        if not identity_service.can_send_code('renter', email):
            return JsonResponse({'error': 'Код уже отправлен. Повторите через минуту.'}, status=429)

        recipient = identity_service.get_plain_email(renter.email)
        if not recipient:
            return JsonResponse({'error': 'Не удалось определить email арендатора'}, status=400)

        code = identity_service.generate_verification_code()
        identity_service.store_verification_code('renter', email, renter.uuid, code)

        if not identity_service.send_verification_email(
            recipient,
            code,
            'Поддержка — подтверждение арендатора',
        ):
            return JsonResponse({'error': 'Не удалось отправить письмо'}, status=500)

        return JsonResponse({
            'found': True,
            'message': 'Код подтверждения отправлен на указанный email',
        })
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_renter_verify_code(request):
    """
    API: Проверка введенного проверочного кода для верификации арендатора
    URL ROUTE: POST /api/identity/renter/verify-code/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()

        if not identity_service.EMAIL_RE.match(email) or not code:
            return JsonResponse({'error': 'Укажите email и код'}, status=400)

        person_uuid = identity_service.verify_code('renter', email, code)
        if not person_uuid:
            return JsonResponse({'error': 'Неверный или просроченный код'}, status=400)

        return JsonResponse({'success': True, 'uuid': person_uuid})
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_renter_register(request):
    """
    API: Регистрация арендатора, если он отсутствует
    URL ROUTE: POST /api/identity/renter/register/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        person_uuid = (data.get('uuid') or '').strip()

        if not identity_service.EMAIL_RE.match(email):
            return JsonResponse({'error': 'Укажите корректный email'}, status=400)
        if not person_uuid:
            return JsonResponse({'error': 'Не указан UUID'}, status=400)
        if identity_service.find_renter_by_email(email):
            return JsonResponse({'error': 'Арендатор с таким email уже существует'}, status=400)
        if Renter.objects.filter(uuid=person_uuid).exists():
            return JsonResponse({'error': 'UUID уже используется'}, status=400)

        renter = Renter.objects.create(
            uuid=person_uuid,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            middle_name=data.get('middle_name') or None,
            phone_number=data.get('phone_number') or None,
            email=email,
        )

        return JsonResponse({
            'success': True,
            'uuid': renter.uuid,
            'message': 'Профиль арендатора создан',
        })
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_grant_person_request_code(request):
    """
    API: Отправка проверочного кода на электронную почту для верификации ответственного лица
    URL ROUTE: POST /api/identity/grant-person/request-code/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        if not identity_service.EMAIL_RE.match(email):
            return JsonResponse({'error': 'Укажите корректный email'}, status=400)

        person = identity_service.find_grant_person_by_email(email)
        if not person:
            return JsonResponse({'found': False})

        if not identity_service.can_send_code('grant_person', email):
            return JsonResponse({'error': 'Код уже отправлен. Повторите через минуту.'}, status=429)

        recipient = identity_service.get_plain_email(person.email)
        if not recipient:
            return JsonResponse({'error': 'Не удалось определить email сотрудника'}, status=400)

        code = identity_service.generate_verification_code()
        identity_service.store_verification_code('grant_person', email, person.uuid, code)

        if not identity_service.send_verification_email(
            recipient,
            code,
            'Панель поддержки — подтверждение сотрудника',
        ):
            return JsonResponse({'error': 'Не удалось отправить письмо'}, status=500)

        return JsonResponse({
            'found': True,
            'message': 'Код подтверждения отправлен на указанный email',
        })
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_grant_person_verify_code(request):
    """
    API: Проверка полученного проверочного кода для верификации ответственного лица
    URL ROUTE: POST /api/identity/grant-person/verify-code/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()

        if not identity_service.EMAIL_RE.match(email) or not code:
            return JsonResponse({'error': 'Укажите email и код'}, status=400)

        person_uuid = identity_service.verify_code('grant_person', email, code)
        if not person_uuid:
            return JsonResponse({'error': 'Неверный или просроченный код'}, status=400)

        return JsonResponse({'success': True, 'uuid': person_uuid})
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)


@require_http_methods(['POST'])
@csrf_exempt
def api_identity_grant_person_register(request):
    """
    API: Регистрация ответственного лица
    URL ROUTE: POST /api/identity/grant-person/register/
    """
    try:
        data = json.loads(request.body or '{}')
        email = (data.get('email') or '').strip()
        person_uuid = (data.get('uuid') or '').strip()

        if not identity_service.EMAIL_RE.match(email):
            return JsonResponse({'error': 'Укажите корректный email'}, status=400)
        if not person_uuid:
            return JsonResponse({'error': 'Не указан UUID'}, status=400)
        if identity_service.find_grant_person_by_email(email):
            return JsonResponse({'error': 'Сотрудник с таким email уже существует'}, status=400)
        if GrantPerson.objects.filter(uuid=person_uuid).exists():
            return JsonResponse({'error': 'UUID уже используется'}, status=400)

        person = GrantPerson.objects.create(
            uuid=person_uuid,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            middle_name=data.get('middle_name') or None,
            phone_number=data.get('phone_number') or None,
            email=email,
        )

        return JsonResponse({
            'success': True,
            'uuid': person.uuid,
            'message': 'Профиль сотрудника создан',
        })
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)
@require_http_methods(['POST'])
@csrf_exempt
def api_support_ticket_message_create(request):
    """
    API: Создание сообщения в тикете поддержки
    URL ROUTE: POST /api/support/ticket/message/create/
    JSON или multipart: ticket_id, sender_id, msg, media[] (до 5 изображений).
    """
    try:
        media_files = []

        if request.content_type.startswith('multipart/'):
            ticket_id = request.POST.get('ticket_id')
            msg_text = (request.POST.get('msg') or '').strip()
            sender_id = (request.POST.get('sender_id') or '').strip()
            media_files = request.FILES.getlist('media')
        else:
            data = json.loads(request.body or '{}')
            ticket_id = data.get('ticket_id')
            msg_text = (data.get('msg') or '').strip()
            sender_id = (data.get('sender_id') or '').strip()

        if not ticket_id or not sender_id:
            return JsonResponse({'error': 'Необходимо указать ticket_id и sender_id'}, status=400)

        if not msg_text and not media_files:
            return JsonResponse({'error': 'Укажите текст или прикрепите изображения'}, status=400)

        if len(msg_text) > 1024:
            return JsonResponse({'error': 'Сообщение не может быть длиннее 1024 символов'}, status=400)

        ticket = get_object_or_404(Ticket.objects.select_related('renter', 'support'), id=ticket_id)

        is_renter_sender = ticket.renter.uuid == sender_id
        is_staff_sender = _is_grant_person_uuid(sender_id)
        if not is_renter_sender and not is_staff_sender:
            return JsonResponse({'error': 'Недопустимый отправитель'}, status=403)

        if is_staff_sender and not ticket.support_id:
            grant_person = GrantPerson.objects.filter(uuid=sender_id).first()
            if grant_person:
                ticket.support = grant_person
                in_work_status = TicketStatus.objects.get_or_create(name='В работе')[0]
                if ticket.status.name == 'Новая':
                    ticket.status = in_work_status
                ticket.save()

        message = TicketMessages.objects.create(
            ticket=ticket,
            msg=msg_text,
            sender_id=sender_id,
            is_read=False,
        )
        support_media_service.save_message_media_files(message, media_files)

        payload = support_media_service.serialize_ticket_message(message, request)
        payload.update({
            'success': True,
            'ticket_id': ticket.pk,
            'support_uuid': ticket.support.uuid if ticket.support else None,
            'renter_uuid': ticket.renter.uuid,
            'message': 'Сообщение успешно отправлено',
        })
        return JsonResponse(payload)

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0] if e.messages else str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e) if settings.DEBUG else 'Что-то пошло не так, попробуйте позже'}, status=400)
