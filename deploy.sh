#!/bin/bash
# SNT Platform — one-shot deploy script
# Run on a fresh Ubuntu 22.04/24.04 server as root
set -e

echo "=== SNT Platform Deploy ==="

# 1. Update system
apt-get update -qq && apt-get install -y -qq git curl

# 2. Install Docker if missing
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
fi

# 3. Clone repo
if [ -d /opt/snt-platform/.git ]; then
  echo "Repo exists, pulling..."
  git -C /opt/snt-platform pull origin main
else
  git clone https://github.com/dimjeb/snt-platform.git /opt/snt-platform
fi
cd /opt/snt-platform

# 4. Create .env
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
  SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${SECRET}|" .env
  sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${SERVER_IP},localhost,127.0.0.1|" .env
  sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://${SERVER_IP}|" .env
  sed -i "s|^DEBUG=.*|DEBUG=False|" .env
  echo ".env created"
fi

# 5. Caddyfile — HTTP on port 80
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
cat > Caddyfile << 'EOF'
:80 {
    reverse_proxy /api/* backend:8000
    reverse_proxy /admin/* backend:8000
    reverse_proxy /static/* backend:8000
    reverse_proxy /media/* backend:8000
    root * /srv/www
    try_files {path} /index.html
    file_server
}
EOF

# 6. Build & start
docker compose build --pull
docker compose up -d

# 7. Wait for DB
echo "Waiting for database..."
for i in $(seq 1 20); do
  docker compose exec -T db pg_isready -U snt &>/dev/null && break || sleep 3
done

# 8. Migrate
docker compose exec -T backend python manage.py migrate --noinput

# 9. Collectstatic
docker compose exec -T backend python manage.py collectstatic --noinput

# 10. Create superadmin with random password
ADMIN_PASS=$(python3 -c "import secrets, string; print(secrets.token_urlsafe(16))")
docker compose exec -T backend python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', '', '${ADMIN_PASS}', role='superadmin')
    print('Superuser created')
else:
    print('Superuser already exists — password unchanged')
"

# 11. Status
docker compose ps

IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo "  SNT Platform deployed successfully!"
echo "  Site:     http://${IP}/"
echo "  Admin:    http://${IP}/admin/"
echo "  Login:    admin"
echo "  Password: ${ADMIN_PASS}"
echo "  (save this password!)"
echo "=========================================="
