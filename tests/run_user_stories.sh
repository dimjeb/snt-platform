#!/usr/bin/env bash
#
# Полный прогон пользовательских историй SNT Платформы.
#
# Делает три шага, которые иначе приходится набирать руками:
#   1. обновляет код на сервере и пересевает тестовые данные
#   2. забирает актуальную версию теста с сервера
#   3. запускает Playwright против боевого адреса
#
# Пересев обязателен перед каждым прогоном: тест пишет в базу (заводит
# члена и участок), поэтому повторный запуск по несвежим данным даёт
# ложные падения.
#
# Использование:
#   ./run_user_stories.sh              # обычный прогон
#   HEADLESS=false ./run_user_stories.sh   # с видимым браузером
#   SKIP_SEED=1 ./run_user_stories.sh      # без пересева
#
set -euo pipefail

SERVER="${SNT_SERVER:-root@87.247.142.223}"
REMOTE_DIR="${SNT_REMOTE_DIR:-/opt/snt-platform}"
BASE_URL="${BASE_URL:-https://snt-platforma.ru}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_FILE="$HERE/playwright_user_stories.py"

if [[ "${SKIP_SEED:-0}" != "1" ]]; then
  echo "==> Обновляю код и пересеваю данные на $SERVER"
  ssh "$SERVER" "cd '$REMOTE_DIR' && git pull -q && \
    docker compose exec -T backend python manage.py seed_test_data --reset 2>&1 | tail -20"
  echo
fi

echo "==> Забираю актуальный тест с сервера"
scp -q "$SERVER:$REMOTE_DIR/tests/playwright_user_stories.py" "$TEST_FILE"
echo

echo "==> Playwright против $BASE_URL"
BASE_URL="$BASE_URL" python "$TEST_FILE"
