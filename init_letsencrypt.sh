#!/bin/sh
# ---------------------------------------------------------------------------
# Первичное получение TLS-сертификата Let's Encrypt для prod-деплоя.
# Запускать ОДИН раз на сервере после настройки .env и DNS (A-запись домена
# должна указывать на этот сервер, порты 80/443 открыты).
#
#   chmod +x init-letsencrypt.sh
#   ./init-letsencrypt.sh
#
# Повторный запуск не нужен — продление делает сервис certbot автоматически.
# ---------------------------------------------------------------------------
set -e

if [ ! -f .env ]; then
  echo "Файл .env не найден. Скопируйте example.env -> .env и заполните его."
  exit 1
fi

# Загружаем DOMAIN и CERTBOT_EMAIL из .env
DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
EMAIL=$(grep -E '^CERTBOT_EMAIL=' .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")

# STAGING=1 — тестовый CA Let's Encrypt (без лимитов, но сертификат «ненастоящий»).
# Поставьте 1 при отладке, потом 0 и перевыпустите.
STAGING=0

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "В .env должны быть заданы DOMAIN и CERTBOT_EMAIL."
  exit 1
fi

# Определяем команду docker compose
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  DC="docker-compose"
fi

echo "### Домен: $DOMAIN, email: $EMAIL"

# Генерируем конфиг nginx с подставленным доменом (без envsubst в контейнере)
echo "### Готовлю конфиг nginx для домена $DOMAIN..."
sed "s|\${DOMAIN}|$DOMAIN|g" nginx/app.conf.template > nginx/app.conf

CERT_PATH="/etc/letsencrypt/live/$DOMAIN"

# 1) Временный самоподписанный сертификат, чтобы nginx смог стартовать на 443
echo "### Создаю временный самоподписанный сертификат..."
$DC run --rm --entrypoint "\
  sh -c 'mkdir -p $CERT_PATH && \
         openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
           -keyout $CERT_PATH/privkey.pem \
           -out $CERT_PATH/fullchain.pem \
           -subj \"/CN=localhost\"'" certbot

# 2) Поднимаем весь стек (nginx стартует на временном сертификате)
echo "### Запускаю контейнеры..."
$DC up -d --build

echo "### Жду запуск nginx..."
sleep 5

# 3) Удаляем временный сертификат
echo "### Удаляю временный сертификат..."
$DC run --rm --entrypoint "rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf" certbot

# 4) Запрашиваем настоящий сертификат через webroot
echo "### Запрашиваю сертификат Let's Encrypt..."
STAGING_ARG=""
if [ "$STAGING" != "0" ]; then STAGING_ARG="--staging"; fi

$DC run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $STAGING_ARG \
    -d $DOMAIN \
    --email $EMAIL \
    --agree-tos --no-eff-email --force-renewal" certbot

# 5) Перезагружаем nginx с боевым сертификатом
echo "### Перезагружаю nginx..."
$DC exec nginx nginx -s reload

echo "### Готово. Сайт доступен по https://$DOMAIN"
