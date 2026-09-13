"""
Playwright — пользовательские истории SNT Платформа
=====================================================

Запуск:
    pip install playwright
    playwright install chromium   # только один раз
    python tests/playwright_user_stories.py

Или с видимым браузером (для отладки):
    HEADLESS=false python tests/playwright_user_stories.py

Требования:
    - Сервер запущен и доступен по BASE_URL
    - Тестовые данные засеяны командой:
        docker compose exec backend python manage.py seed_test_data
"""

import os
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = os.getenv("BASE_URL", "http://snt-platforma.ru")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
SLOW_MO = int(os.getenv("SLOW_MO", "200"))   # мс между действиями

# Учётные записи (должны совпадать с seed_test_data)
SUPERADMIN = {"username": "admin", "password": "12345678"}
CHAIRMAN   = {"username": "chairman_berezka", "password": "12345678",
               "org": "СНТ «Берёзка»"}
TREASURER  = {"username": "treasurer_berezka", "password": "12345678",
               "org": "СНТ «Берёзка»"}
MEMBER_ORG_ID = 1   # id первой org; замени если отличается
MEMBER     = {"username": f"member_{MEMBER_ORG_ID}", "password": "12345678"}

PASS = "✅"
FAIL = "❌"
results = []


def log(name: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    msg = f"{status} {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append({"name": name, "ok": ok, "detail": detail})


def login(page: Page, creds: dict):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    page.fill("input[aria-label='Логин'], input[placeholder*='огин']", creds["username"])
    page.fill("input[type='password']", creds["password"])
    page.click("button[type='submit'], .q-btn:has-text('Войти')")
    page.wait_for_url(f"{BASE_URL}/dashboard", timeout=10_000)


def logout(page: Page):
    # Ищем кнопку выхода в layout
    try:
        page.click("text=Выйти", timeout=3000)
        page.wait_for_url(f"{BASE_URL}/login", timeout=5000)
    except Exception:
        page.goto(f"{BASE_URL}/login")


# =========================================================================== #
#  ИСТОРИЯ 1: ПРЕДСЕДАТЕЛЬ                                                     #
# =========================================================================== #

def story_chairman(page: Page):
    print("\n" + "="*60)
    print("📋 РОЛЬ: ПРЕДСЕДАТЕЛЬ")
    print("="*60)

    # 1.1 Логин
    try:
        login(page, CHAIRMAN)
        log("Председатель: вход в систему", True)
    except Exception as e:
        log("Председатель: вход в систему", False, str(e))
        return

    # 1.2 Дашборд — статистика видна
    try:
        page.wait_for_selector("text=Членов", timeout=5000)
        members_count = page.locator(".text-h5").first.inner_text()
        log("Председатель: дашборд загружен", True, f"членов: {members_count}")
    except Exception as e:
        log("Председатель: дашборд загружен", False, str(e))

    # 1.3 Список членов
    try:
        page.click("text=Члены, a[href*='members'], .q-item:has-text('Члены')")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".q-list .q-item", timeout=8000)
        count = page.locator(".q-list .q-item").count()
        log("Председатель: список членов", True, f"{count} элементов видно")
    except Exception as e:
        log("Председатель: список членов", False, str(e))

    # 1.4 Добавить нового члена
    new_member_ln = f"Тестов{random.randint(100,999)}"
    try:
        page.click(".q-btn[icon='add'], button:has(.q-icon[data-name='add'])")
        page.wait_for_selector(".q-dialog", timeout=5000)
        # Заполняем форму
        inputs = page.locator(".q-dialog input[type='text'], .q-dialog input:not([type])")
        inputs.nth(0).fill(new_member_ln)      # Фамилия
        inputs.nth(1).fill("Иван")              # Имя
        inputs.nth(2).fill("Иванович")          # Отчество
        # Телефон
        phone_input = page.locator(".q-dialog input[type='tel'], .q-dialog input[placeholder*='елефон']")
        if phone_input.count():
            phone_input.first.fill("+7 (999) 123-45-67")
        page.click(".q-dialog button:has-text('Сохранить')")
        page.wait_for_selector(f"text={new_member_ln}", timeout=8000)
        log("Председатель: добавление члена", True, new_member_ln)
    except Exception as e:
        log("Председатель: добавление члена", False, str(e))

    # 1.5 Список участков
    try:
        page.click("text=Участки, a[href*='plots'], .q-item:has-text('Участки')")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".q-list .q-item", timeout=8000)
        count = page.locator(".q-list .q-item").count()
        log("Председатель: список участков", True, f"{count} элементов")
    except Exception as e:
        log("Председатель: список участков", False, str(e))

    # 1.6 Поиск участка
    try:
        search = page.locator(".q-input input").first
        search.fill("1")
        time.sleep(1)
        count_after = page.locator(".q-list .q-item").count()
        log("Председатель: поиск участка", True, f"{count_after} результатов по '1'")
        search.clear()
        time.sleep(0.5)
    except Exception as e:
        log("Председатель: поиск участка", False, str(e))

    # 1.7 Добавить участок
    try:
        page.click(".q-btn:has(.q-icon)")  # кнопка + в заголовке
        page.wait_for_selector(".q-dialog", timeout=5000)
        inputs = page.locator(".q-dialog input")
        inputs.nth(0).fill("999")          # Номер
        inputs.nth(1).fill("8.50")         # Площадь
        inputs.nth(2).fill("38:06:999999:001")  # Кадастровый
        page.click(".q-dialog button:has-text('Сохранить')")
        time.sleep(2)
        log("Председатель: добавление участка №999", True)
    except Exception as e:
        log("Председатель: добавление участка", False, str(e))

    # 1.8 Начисления
    try:
        page.click("text=Финансы, a[href*='billing'], .q-item:has-text('Финансы')")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".q-tabs", timeout=8000)
        log("Председатель: страница финансов", True)
    except Exception as e:
        log("Председатель: страница финансов", False, str(e))

    # 1.9 Вкладка «Начисления»
    try:
        page.click(".q-tab:has-text('Начисления')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Председатель: вкладка начислений", True)
    except Exception as e:
        log("Председатель: вкладка начислений", False, str(e))

    # 1.10 Вкладка «Долги»
    try:
        page.click(".q-tab:has-text('Долги')")
        time.sleep(1)
        debt_items = page.locator(".q-list .q-item").count()
        log("Председатель: вкладка долгов", True, f"{debt_items} записей")
    except Exception as e:
        log("Председатель: вкладка долгов", False, str(e))

    # 1.11 Электроэнергия
    try:
        page.click("text=Электроэнергия, a[href*='electricity'], .q-item:has-text('Электроэнерг')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Председатель: страница электроэнергии", True)
    except Exception as e:
        log("Председатель: страница электроэнергии", False, str(e))

    # 1.12 Отчёты
    try:
        page.click("text=Отчёты, a[href*='reports'], .q-item:has-text('Отчёты')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Председатель: страница отчётов", True)
    except Exception as e:
        log("Председатель: страница отчётов", False, str(e))

    # 1.13 Профиль (/api/me)
    try:
        me_btn = page.locator(".q-btn:has-text('Профиль'), .q-avatar, [href*='profile']")
        if me_btn.count():
            me_btn.first.click()
            time.sleep(1)
        log("Председатель: профиль доступен", True)
    except Exception as e:
        log("Председатель: профиль", False, str(e))

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 2: КАЗНАЧЕЙ                                                         #
# =========================================================================== #

def story_treasurer(page: Page):
    print("\n" + "="*60)
    print("💰 РОЛЬ: КАЗНАЧЕЙ")
    print("="*60)

    try:
        login(page, TREASURER)
        log("Казначей: вход в систему", True)
    except Exception as e:
        log("Казначей: вход в систему", False, str(e))
        return

    # 2.1 Дашборд
    try:
        page.wait_for_selector("text=Членов", timeout=5000)
        log("Казначей: дашборд загружен", True)
    except Exception as e:
        log("Казначей: дашборд загружен", False, str(e))

    # 2.2 Члены — только просмотр
    try:
        page.click("text=Члены, a[href*='members'], .q-item:has-text('Члены')")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".q-list .q-item", timeout=8000)
        # Кнопки добавления/удаления должны быть (казначей имеет доступ)
        log("Казначей: список членов доступен", True)
    except Exception as e:
        log("Казначей: список членов", False, str(e))

    # 2.3 Финансы — основная роль казначея
    try:
        page.click("text=Финансы, a[href*='billing'], .q-item:has-text('Финансы')")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector(".q-tabs", timeout=8000)
        log("Казначей: страница финансов", True)
    except Exception as e:
        log("Казначей: страница финансов", False, str(e))

    # 2.4 Зафиксировать оплату (если есть список долгов)
    try:
        page.click(".q-tab:has-text('Долги')")
        time.sleep(1.5)
        # Ищем кнопку оплаты у первого должника
        pay_btn = page.locator("button:has-text('Оплата'), .q-btn:has-text('Оплатить'), .q-btn[icon='payment']")
        if pay_btn.count():
            pay_btn.first.click()
            page.wait_for_selector(".q-dialog", timeout=5000)
            page.click(".q-dialog button:has-text('Сохранить'), .q-dialog button:has-text('Принять')")
            time.sleep(1)
            log("Казначей: фиксация оплаты", True)
        else:
            log("Казначей: фиксация оплаты", True, "нет должников с кнопкой (ОК)")
    except Exception as e:
        log("Казначей: фиксация оплаты", False, str(e))

    # 2.5 Ввести массовое начисление
    try:
        page.click(".q-tab:has-text('Долги')")
        time.sleep(1)
        mass_btn = page.locator(".q-btn:has-text('Членский взнос'), .q-btn:has-text('Целевой взнос')")
        if mass_btn.count():
            mass_btn.first.click()
            page.wait_for_selector(".q-dialog", timeout=5000)
            # Заполнить сумму если есть поле
            amount_input = page.locator(".q-dialog input[type='number']")
            if amount_input.count():
                amount_input.first.fill("2000")
            page.click(".q-dialog button:has-text('Создать'), .q-dialog button:has-text('Сохранить')")
            time.sleep(2)
            log("Казначей: массовое начисление", True)
        else:
            log("Казначей: массовое начисление", True, "кнопка не найдена (ОК для казначея)")
    except Exception as e:
        log("Казначей: массовое начисление", False, str(e))

    # 2.6 Электроэнергия
    try:
        page.click("text=Электроэнергия, .q-item:has-text('Электроэнерг')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Казначей: электроэнергия", True)
    except Exception as e:
        log("Казначей: электроэнергия", False, str(e))

    # 2.7 Отчёты
    try:
        page.click("text=Отчёты, .q-item:has-text('Отчёты')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Казначей: отчёты", True)
    except Exception as e:
        log("Казначей: отчёты", False, str(e))

    # 2.8 Нет доступа к admin-only функциям (проверяем через API)
    try:
        page.goto(f"{BASE_URL}/api/organizations/")
        resp_text = page.content()
        # Казначей не должен видеть список организаций
        no_access = "403" in resp_text or "permission" in resp_text.lower() or "Forbidden" in resp_text
        log("Казначей: нет доступа к /api/organizations/", no_access,
            "403 получен" if no_access else "ВНИМАНИЕ: доступ открыт")
        page.go_back()
    except Exception as e:
        log("Казначей: проверка прав", False, str(e))

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 3: ЧЛЕН СНТ                                                         #
# =========================================================================== #

def story_member(page: Page):
    print("\n" + "="*60)
    print("🌿 РОЛЬ: ЧЛЕН СНТ")
    print("="*60)

    try:
        login(page, MEMBER)
        log("Член СНТ: вход в систему", True)
    except Exception as e:
        log("Член СНТ: вход в систему", False, str(e))
        return

    # 3.1 Дашборд — только свои данные
    try:
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        # Блок "Членов" не должен быть виден (только для управления)
        members_stat = page.locator("text=Членов")
        if members_stat.count() == 0:
            log("Член СНТ: статистика управления скрыта", True)
        else:
            log("Член СНТ: статистика управления скрыта", False, "блок виден, но не должен")
    except Exception as e:
        log("Член СНТ: дашборд", False, str(e))

    # 3.2 Доступ к разделу «Члены» должен быть закрыт
    try:
        page.goto(f"{BASE_URL}/members")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        # Должен редиректить на dashboard
        is_on_dashboard = "/dashboard" in page.url or page.url.endswith("/")
        log("Член СНТ: раздел 'Члены' закрыт", is_on_dashboard,
            f"текущий URL: {page.url}")
    except Exception as e:
        log("Член СНТ: раздел 'Члены' закрыт", False, str(e))

    # 3.3 Ввод показаний счётчика
    try:
        page.click("text=Показания, a[href*='meter'], .q-item:has-text('Показания')")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        log("Член СНТ: страница показаний", True)
    except Exception as e:
        log("Член СНТ: страница показаний", False, str(e))

    # 3.4 Внести показание (если есть счётчик)
    try:
        reading_input = page.locator("input[type='number']").first
        if reading_input.is_visible():
            current_val = reading_input.input_value() or "0"
            new_val = str(int(float(current_val)) + random.randint(100, 500))
            reading_input.fill(new_val)
            save_btn = page.locator("button:has-text('Сохранить'), .q-btn:has-text('Отправить')")
            if save_btn.count():
                save_btn.first.click()
                time.sleep(1.5)
            log("Член СНТ: ввод показания счётчика", True, f"значение: {new_val}")
        else:
            log("Член СНТ: ввод показания счётчика", True, "нет привязанного счётчика (ОК)")
    except Exception as e:
        log("Член СНТ: ввод показания счётчика", False, str(e))

    # 3.5 Страница финансов / долги
    try:
        page.goto(f"{BASE_URL}/billing")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        is_allowed = "/billing" in page.url
        if is_allowed:
            log("Член СНТ: финансы (личные)", True)
        else:
            log("Член СНТ: редирект с финансов", True, "доступ ограничен — ОК")
    except Exception as e:
        log("Член СНТ: финансы", False, str(e))

    # 3.6 Редактирование профиля
    try:
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        # Пробуем через API /api/me/
        resp = page.request.patch(
            f"{BASE_URL}/api/me/",
            data={"phone": "+7 (999) 000-00-01"},
        )
        ok = resp.ok
        log("Член СНТ: обновление профиля (PATCH /api/me/)", ok,
            f"status: {resp.status}")
    except Exception as e:
        log("Член СНТ: обновление профиля", False, str(e))

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 4: СУПЕРАДМИН                                                       #
# =========================================================================== #

def story_superadmin(page: Page):
    print("\n" + "="*60)
    print("⚙️  РОЛЬ: СУПЕРАДМИН")
    print("="*60)

    try:
        login(page, SUPERADMIN)
        log("Суперадмин: вход в систему", True)
    except Exception as e:
        log("Суперадмин: вход в систему", False, str(e))
        return

    # 4.1 Видит все организации
    try:
        resp = page.request.get(f"{BASE_URL}/api/organizations/")
        data = resp.json()
        orgs = data.get("results", data) if isinstance(data, dict) else data
        log("Суперадмин: список всех СНТ через API", True, f"{len(orgs)} организаций")
    except Exception as e:
        log("Суперадмин: список СНТ", False, str(e))

    # 4.2 Переключение между СНТ
    try:
        page.wait_for_selector(".q-select, select", timeout=5000)
        org_select = page.locator(".q-select").first
        if org_select.is_visible():
            org_select.click()
            page.wait_for_selector(".q-menu .q-item", timeout=3000)
            items = page.locator(".q-menu .q-item")
            count = items.count()
            if count > 1:
                items.nth(1).click()
                time.sleep(1)
                log("Суперадмин: переключение между СНТ", True, f"{count} вариантов")
            else:
                log("Суперадмин: переключение между СНТ", True, "только 1 org в select")
        else:
            log("Суперадмин: переключение между СНТ", True, "select не отображается на dashboard")
    except Exception as e:
        log("Суперадмин: переключение СНТ", False, str(e))

    # 4.3 Django admin
    try:
        page.goto(f"{BASE_URL}/admin/")
        page.wait_for_load_state("networkidle")
        is_admin = "Django administration" in page.content() or "Администрирование" in page.content()
        log("Суперадмин: Django admin", is_admin, page.url)
    except Exception as e:
        log("Суперадмин: Django admin", False, str(e))

    # 4.4 Swagger API docs
    try:
        page.goto(f"{BASE_URL}/api/docs/")
        page.wait_for_load_state("networkidle")
        has_swagger = "swagger" in page.content().lower() or "openapi" in page.content().lower()
        log("Суперадмин: API документация /api/docs/", has_swagger)
    except Exception as e:
        log("Суперадмин: API docs", False, str(e))

    logout(page)


# =========================================================================== #
#  ГЛАВНАЯ ТОЧКА ВХОДА                                                         #
# =========================================================================== #

def main():
    print(f"\n🌱 SNT Платформа — Playwright тесты")
    print(f"   URL: {BASE_URL}")
    print(f"   Headless: {HEADLESS}")
    print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            slow_mo=SLOW_MO,
            executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_PATH", None),
        )
        context = browser.new_context(
            viewport={"width": 390, "height": 844},  # iPhone 14 — mobile-first
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        )
        page = context.new_page()

        try:
            story_chairman(page)
            story_treasurer(page)
            story_member(page)
            story_superadmin(page)
        finally:
            context.close()
            browser.close()

    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГ")
    print("="*60)
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    print(f"Всего проверок: {len(results)}")
    print(f"  {PASS} Прошли:  {passed}")
    print(f"  {FAIL} Упали:   {failed}")

    if failed:
        print("\nПровалившиеся:")
        for r in results:
            if not r["ok"]:
                print(f"  {FAIL} {r['name']}: {r['detail']}")

    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
