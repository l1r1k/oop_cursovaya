#!/bin/sh
set -e

FERNET_FILE="/app/fernet/fernet.key"

DB_WAIT_HOST="${DB_HOST:-db}"
DB_WAIT_PORT="${DB_PORT:-5432}"

echo "Waiting for postgres at ${DB_WAIT_HOST}:${DB_WAIT_PORT}..."
while ! nc -z "$DB_WAIT_HOST" "$DB_WAIT_PORT"; do
  sleep 1
done
echo "PostgreSQL started"

if [ ! -f "$FERNET_FILE" ]; then
  echo "Generating new Fernet key..."
  python - << END
from cryptography.fernet import Fernet
with open("$FERNET_FILE", "wb") as f:
    f.write(Fernet.generate_key())
END
  echo "Fernet key generated"
else
  echo "Fernet key exists"
fi

export FERNET_KEY=$(cat "$FERNET_FILE")

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static..."
python manage.py collectstatic --noinput

echo "Creating superuser if not exists..."
python manage.py shell << END
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.getenv('DJANGO_SUPERUSER_USERNAME')
email = os.getenv('DJANGO_SUPERUSER_EMAIL')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
if username and password and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
END

echo "Starting Gunicorn..."
exec gunicorn rent_costumes.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --access-logfile - \
  --error-logfile -