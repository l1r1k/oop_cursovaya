from datetime import timedelta

from django.utils import timezone

from .models import Ticket, TicketMessages, TicketStatus

CLOSED_STATUS_NAME = 'Закрыта'
STAFF_CLOSE_AFTER_HOURS = 24


def get_closed_status():
    return TicketStatus.objects.get_or_create(name=CLOSED_STATUS_NAME)[0]


def is_ticket_closed(ticket: Ticket) -> bool:
    return ticket.status.name == CLOSED_STATUS_NAME


def get_renter_open_ticket(renter_uuid: str):
    return (
        Ticket.objects.filter(renter__uuid=renter_uuid)
        .exclude(status__name=CLOSED_STATUS_NAME)
        .select_related('status', 'renter')
        .order_by('-created_at')
        .first()
    )


def get_last_ticket_message(ticket_id: int):
    return (
        TicketMessages.objects.filter(ticket_id=ticket_id)
        .order_by('-created_at')
        .first()
    )


def staff_close_deadline_reached(ticket: Ticket) -> bool:
    return timezone.now() >= ticket.created_at + timedelta(hours=STAFF_CLOSE_AFTER_HOURS)


def evaluate_close_permission(ticket: Ticket, renter_uuid: str | None, grant_person_uuid: str | None) -> dict:
    """
    Возвращает can_close, close_hint, closed_by (renter|staff|null)
    """
    if is_ticket_closed(ticket):
        return {
            'can_close': False,
            'close_hint': 'Заявка уже закрыта',
            'is_closed': True,
        }

    last_message = get_last_ticket_message(ticket.pk)
    renter_id = ticket.renter.uuid

    if renter_uuid and ticket.renter.uuid == renter_uuid:
        if not last_message:
            return {
                'can_close': False,
                'close_hint': 'Дождитесь ответа поддержки',
                'is_closed': False,
            }
        if last_message.sender_id == renter_id:
            return {
                'can_close': False,
                'close_hint': 'Закрыть заявку можно только после ответа поддержки',
                'is_closed': False,
            }
        return {
            'can_close': True,
            'close_hint': '',
            'is_closed': False,
        }

    if grant_person_uuid:
        if not staff_close_deadline_reached(ticket):
            remaining = ticket.created_at + timedelta(hours=STAFF_CLOSE_AFTER_HOURS) - timezone.now()
            hours = max(1, int(remaining.total_seconds() // 3600) + (1 if remaining.total_seconds() % 3600 else 0))
            return {
                'can_close': False,
                'close_hint': (
                    f'Сотрудник может закрыть заявку через 24 ч после создания '
                    f'(осталось около {hours} ч.)'
                ),
                'is_closed': False,
            }
        return {
            'can_close': True,
            'close_hint': '',
            'is_closed': False,
        }

    return {
        'can_close': False,
        'close_hint': 'Недостаточно прав для закрытия',
        'is_closed': False,
    }
