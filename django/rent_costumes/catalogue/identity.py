import hashlib
import secrets
import re

from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

from .encryption import decrypt_field
from .models import Renter, GrantPerson

CODE_TTL_SECONDS = 600
CODE_SEND_COOLDOWN_SECONDS = 60
MAX_VERIFY_ATTEMPTS = 5
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_cache_key(entity_type: str, email: str) -> str:
    digest = hashlib.sha256(normalize_email(email).encode('utf-8')).hexdigest()
    return f'identity:{entity_type}:{digest}'


def send_cooldown_key(entity_type: str, email: str) -> str:
    return f'identity:sent:{entity_type}:{normalize_email(email)}'


def get_plain_email(email_field) -> str | None:
    if not email_field:
        return None
    value = str(email_field)
    if '@' in value:
        return value
    try:
        return decrypt_field(email_field)
    except Exception:
        return None


def emails_match(stored_email, requested_email: str) -> bool:
    plain = get_plain_email(stored_email)
    if not plain:
        return False
    return plain.strip().lower() == normalize_email(requested_email)


def find_renter_by_email(email: str):
    for renter in Renter.objects.all():
        if renter.email and emails_match(renter.email, email):
            return renter
    return None


def find_grant_person_by_email(email: str):
    for person in GrantPerson.objects.all():
        if person.email and emails_match(person.email, email):
            return person
    return None


def generate_verification_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def store_verification_code(entity_type: str, email: str, person_uuid: str, code: str) -> None:
    cache.set(
        email_cache_key(entity_type, email),
        {
            'code': code,
            'uuid': person_uuid,
            'attempts': 0,
        },
        CODE_TTL_SECONDS,
    )
    cache.set(send_cooldown_key(entity_type, email), True, CODE_SEND_COOLDOWN_SECONDS)


def can_send_code(entity_type: str, email: str) -> bool:
    return not cache.get(send_cooldown_key(entity_type, email))


def verify_code(entity_type: str, email: str, code: str) -> str | None:
    key = email_cache_key(entity_type, email)
    payload = cache.get(key)
    if not payload:
        return None

    payload['attempts'] = payload.get('attempts', 0) + 1
    if payload['attempts'] > MAX_VERIFY_ATTEMPTS:
        cache.delete(key)
        return None

    cache.set(key, payload, CODE_TTL_SECONDS)

    if str(payload.get('code')) != str(code).strip():
        return None

    cache.delete(key)
    return payload.get('uuid')


def send_verification_email(recipient_email: str, code: str, title: str) -> bool:
    try:
        html_message = render_to_string('email/email_verification_code.html', {
            'code': code,
            'title': title,
        })
        plain_message = strip_tags(html_message)
        send_mail(
            subject=f'{title} — код подтверждения',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        print(f'Error sending verification email: {exc}')
        return False
