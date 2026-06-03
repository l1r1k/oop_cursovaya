from django.core.exceptions import ValidationError

from .models import MediaTicketMessages
from .validators import validate_image_size, validate_photo_format

MAX_MEDIA_PER_MESSAGE = 5


def message_preview_text(msg_obj) -> str:
    text = (msg_obj.msg or '').strip()
    if text:
        return text
    if msg_obj.medias.exists():
        count = msg_obj.medias.count()
        if count == 1:
            return 'Изображение'
        return f'{count} изображения'
    return ''


def serialize_message_media(message, request=None) -> list[dict]:
    items = []
    for media_obj in message.medias.all():
        url = media_obj.media.url
        if request is not None:
            url = request.build_absolute_uri(url)
        items.append({
            'id': media_obj.pk,
            'url': url,
        })
    return items


def serialize_ticket_message(message, request=None) -> dict:
    text = (message.msg or '').strip()
    return {
        'msg_id': message.pk,
        'msg': text,
        'sender_id': message.sender_id,
        'datetime': message.created_at,
        'media': serialize_message_media(message, request),
    }


def save_message_media_files(message, files) -> list[dict]:
    if not files:
        return []

    if len(files) > MAX_MEDIA_PER_MESSAGE:
        raise ValidationError(f'Можно прикрепить не более {MAX_MEDIA_PER_MESSAGE} изображений')

    saved = []
    for uploaded in files:
        validate_photo_format(uploaded)
        validate_image_size(uploaded)
        media_obj = MediaTicketMessages.objects.create(
            ticket_message=message,
            media=uploaded,
        )
        saved.append(media_obj)
    return saved
