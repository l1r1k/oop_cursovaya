"""
URL конфигурация для приложения костюмов
"""
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .forms import CustomAuthForm

app_name = 'costumes'

urlpatterns = [
    # СТРАНИЦЫ (HTML)
    path('', views.catalog_page, name='catalog'),
    path('costume/<int:costume_id>/', views.costume_detail_page, name='costume_detail'),
    path('cart/', views.cart_page, name='cart'),
    path('track/', views.track_request_page, name='track_request'),
    path('support/', views.support_page, name='support'),
    path('manager-panel/', views.manager_page, name='manager'),
    path('support-panel/', views.support_panel_page, name='support-panel'),
    
    # API - КАТАЛОГ
    path('api/catalog/filters/', views.api_catalog_filters, name='api_catalog_filters'),
    path('api/catalog/list/', views.api_catalog_list, name='api_catalog_list'),
    
    # API - ДЕТАЛИ КОСТЮМА
    path('api/costume/<int:costume_id>/', views.api_costume_detail, name='api_costume_detail'),
    
    # API - КОРЗИНА
    path('api/cart/add/', views.api_cart_add, name='api_cart_add'),
    path('api/cart/update/', views.api_cart_update, name='api_cart_update'),
    
    # API - ЗАЯВКИ
    path('api/request/create/', views.api_create_request, name='api_create_request'),
    path('api/request/<int:request_id>/track/', views.api_track_request, name='api_track_request'),
    
    # API - МЕНЕДЖЕР
    path('api/manager/stats/', views.api_manager_stats, name='api_manager_stats'),
    path('api/manager/requests/', views.api_manager_requests, name='api_manager_requests'),
    path('api/manager/rents/', views.api_manager_rents, name='api_manager_rents'),
    path('api/manager/statuses/', views.api_manager_statuses, name='api_manager_statuses'),
    path('api/manager/request/<int:request_id>/status/', views.api_manager_update_request_status, name='api_manager_update_request_status'),
    path('api/manager/rent/<int:rent_id>/status/', views.api_manager_update_rent_status, name='api_manager_update_rent_status'),
    path('api/manager/request/<int:request_id>/create-rent/', views.api_manager_create_rent, name='api_manager_create_rent'),
    path('api/manager/requests/<int:id>/items/', views.api_manager_requests_items, name='api_manager_requests_items'),
    
    # АВТОРИЗАЦИЯ
    path('login/', auth_views.LoginView.as_view(
        template_name='auth/login.html',
        authentication_form=CustomAuthForm)
        , name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # API - проверка доступности костюма по количеству
    path('api/costume/<int:costume_id>/availability/', 
         views.api_costume_availability, 
         name='api_costume_availability'),

    # API - Тех. поддержка
    path('api/support/ticket/create/',
         views.api_support_ticket_create,
         name='api_support_ticket_create'),
    path('api/support/ticket/<int:ticket_id>/close/',
         views.api_support_ticket_close,
         name='api_support_ticket_close'),
    path('api/support/tickets/',
         views.api_support_tickets,
         name='api_support_tickets'),
    path('api/support/ticket/<int:ticket_id>/ticket-messages/',
         views.api_support_ticket_ticket_messages,
         name='api_support_ticket_ticket_messages'),
    path('api/support/ticket/<int:ticket_id>/last-message/',
         views.api_support_ticket_last_message,
         name='api_support_ticket_last_message'),

    # API - Проверка существования арендатора
    path('api/support/ticket/message/create/',
         views.api_support_ticket_message_create,
         name='api_support_ticket_message_create'),

    path('api/renter/<str:renter_uuid>/',
         views.api_renter_exist,
         name='api_renter_exist'),

    # API — идентификация для чата поддержки (UUID + email)
    path('api/identity/renter/<str:renter_uuid>/check/',
         views.api_identity_renter_check,
         name='api_identity_renter_check'),
    path('api/identity/grant-person/<str:grant_person_uuid>/check/',
         views.api_identity_grant_person_check,
         name='api_identity_grant_person_check'),
    path('api/identity/renter/request-code/',
         views.api_identity_renter_request_code,
         name='api_identity_renter_request_code'),
    path('api/identity/renter/verify-code/',
         views.api_identity_renter_verify_code,
         name='api_identity_renter_verify_code'),
    path('api/identity/renter/register/',
         views.api_identity_renter_register,
         name='api_identity_renter_register'),
    path('api/identity/grant-person/request-code/',
         views.api_identity_grant_person_request_code,
         name='api_identity_grant_person_request_code'),
    path('api/identity/grant-person/verify-code/',
         views.api_identity_grant_person_verify_code,
         name='api_identity_grant_person_verify_code'),
    path('api/identity/grant-person/register/',
         views.api_identity_grant_person_register,
         name='api_identity_grant_person_register'),
]