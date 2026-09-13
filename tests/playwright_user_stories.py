"""
Playwright — пользовательские истории SNT Платформа
=====================================================

Запуск:
    pip install playwright
    playwright install chromium   # только один раз
    BASE_URL=https://snt-platforma.ru python tests/playwright_user_stories.py

Или с видимым браузером (для отладки):
    HEADLESS=false SLOW_MO=600 BASE_URL=https://snt-platforma.ru python tests/playwright_user_stories.py

Требования:
    - Сервер доступен по BASE_URL. Схема должна совпадать с фактической:
      сервер отдаёт 308 с http на https, поэтому BASE_URL=https://...
    - Тестовые данные засеяны командой:
        docker compose exec backend python manage.py seed_test_data --clear

Навигация идёт прямо по URL, а не кликами по боковому меню: меню объявлено
как <q-drawer behavior="mobile"> и при мобильном viewport закрыто по умолчанию,
так что его пунктов на экране нет, пока не нажат гамбургер.
"""

import os
import random
from datetime import datetime, date
from playwright.sync_api import sync_playwright, Page

BASE_URL = os.getenv("BASE_URL", "https://snt-platforma.ru").rstrip("/")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"
SLOW_MO = int(os.getenv("SLOW_MO", "200"))       # мс между действиями
TIMEOUT = int(os.getenv("TIMEOUT", "20000"))     # мс на ожидание элемента
NAV_TIMEOUT = int(os.getenv("NAV_TIMEOUT", "40000"))  # мс на переход между страницами

# Учётные записи (должны совпадать с seed_test_data)
SUPERADMIN = {"username": "admin", "password": "12345678"}
CHAIRMAN   = {"username": "chairman_berezka", "password": "12345678",
              "org": "СНТ «Берёзка»"}
TREASURER  = {"username": "treasurer_berezka", "password": "12345678",
              "org": "СНТ «Берёзка»"}
MEMBER     = {"username": "member_berezka", "password": "12345678"}

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


# =========================================================================== #
#  Хелперы                                                                     #
# =========================================================================== #

def login(page: Page, creds: dict):
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    settle(page)
    page.fill("input[aria-label='Логин'], input[placeholder*='огин']", creds["username"])
    page.fill("input[type='password']", creds["password"])
    page.click("button[type='submit'], .q-btn:has-text('Войти')")
    page.wait_for_url(f"{BASE_URL}/dashboard", timeout=NAV_TIMEOUT)


def logout(page: Page):
    """Разлогин через localStorage — надёжнее, чем искать кнопку в закрытом меню."""
    try:
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
    except Exception:
        pass
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    settle(page)


def settle(page: Page):
    """Дождаться затишья в сети, но не падать, если оно не наступает."""
    try:
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
    except Exception:
        pass


def goto(page: Page, path: str) -> str:
    """Переход по прямому URL. Возвращает фактический адрес после роутинга."""
    page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    settle(page)
    return page.url


def icon_btn(page: Page, icon_name: str):
    """
    Quasar не сохраняет icon="add" как атрибут DOM — при наборе material-icons
    он рендерит <i class="q-icon material-icons">add</i>, то есть имя иконки
    лежит текстом. Ограничиваемся .q-page: в шапке и боковом меню свои кнопки.
    """
    return page.locator(f'.q-page .q-btn:has-text("{icon_name}")')


def describe_buttons(page: Page) -> str:
    """Что за кнопки есть на странице — чтобы упавший селектор было чем чинить."""
    try:
        return page.evaluate(
            """() => Array.from(document.querySelectorAll('.q-page .q-btn'))
                .slice(0, 8)
                .map(b => (b.innerText || '').trim() || '[без текста]')
                .join(' | ') || 'кнопок в .q-page нет'"""
        )
    except Exception as e:
        return f"не удалось осмотреть страницу: {e}"


def dialog_input(page: Page, label: str):
    """Поле открытого диалога по тексту его плавающей подписи."""
    return page.locator(
        f'.q-dialog .q-field:has(.q-field__label:text-is("{label}")) input'
    )


def stat_value(page: Page, caption: str) -> str:
    """Число из карточки дашборда по подписи под ним."""
    loc = page.locator(f'.q-card:has(.text-caption:text-is("{caption}")) .text-h5')
    return loc.first.inner_text().strip()


def row_count(page: Page, empty_text: str) -> int:
    """
    Число строк в q-list внутри .q-page.

    Скоуп обязателен: боковое меню — тоже q-list с q-item, и висит в DOM
    даже закрытым. Без .q-page счётчик показывал 58 пунктов меню вместо
    реальных записей, из-за чего проверки проходили вхолостую.
    """
    if page.locator(f'.q-page .q-item:has-text("{empty_text}")').count() > 0:
        return 0
    return page.locator(".q-page .q-list .q-item").count()


def api_status(page: Page, path: str) -> int:
    """Статус ответа API с токеном текущего пользователя."""
    return page.evaluate(
        """async (p) => {
            const token = localStorage.getItem('access') || '';
            const r = await fetch(p, { headers: { Authorization: 'Bearer ' + token } });
            return r.status;
        }""",
        path,
    )


# =========================================================================== #
#  ИСТОРИЯ 1: ПРЕДСЕДАТЕЛЬ                                                     #
# =========================================================================== #

def story_chairman(page: Page):
    print("\n" + "=" * 60)
    print("📋 РОЛЬ: ПРЕДСЕДАТЕЛЬ")
    print("=" * 60)

    try:
        login(page, CHAIRMAN)
        log("Председатель: вход в систему", True)
    except Exception as e:
        log("Председатель: вход в систему", False, str(e)[:200])
        return

    # 1.1 Дашборд. networkidle — чтобы дождаться onMounted-запросов,
    #     иначе карточки читаются с начальных нулей.
    try:
        settle(page)
        members = stat_value(page, "Членов")
        plots = stat_value(page, "Участков")
        ok = members.isdigit() and int(members) > 0
        log("Председатель: дашборд со статистикой", ok,
            f"членов: {members}, участков: {plots}"
            + ("" if ok else " — ожидались данные seed, проверь что seed отработал"))
    except Exception as e:
        log("Председатель: дашборд со статистикой", False, str(e)[:200])

    # 1.2 Список членов
    try:
        goto(page, "/members")
        page.wait_for_selector(".q-page .q-list .q-item", timeout=TIMEOUT)
        count = row_count(page, "Нет членов")
        log("Председатель: список членов", count > 0, f"{count} строк")
    except Exception as e:
        log("Председатель: список членов", False, str(e)[:200])

    # 1.3 Добавление члена
    new_ln = f"Тестов{random.randint(1000, 9999)}"
    try:
        icon_btn(page, "add").first.click()
        page.wait_for_selector(".q-dialog", timeout=TIMEOUT)
        dialog_input(page, "Фамилия *").fill(new_ln)
        dialog_input(page, "Имя *").fill("Тест")
        dialog_input(page, "Телефон").fill("+7 (999) 000-11-22")
        page.click('.q-dialog .q-btn:has-text("Сохранить")')
        page.wait_for_selector(".q-dialog", state="hidden", timeout=TIMEOUT)
        settle(page)
        page.fill('input[placeholder*="Поиск"]', new_ln)
        page.wait_for_timeout(1200)          # debounce поиска
        found = page.locator(f'.q-item:has-text("{new_ln}")').count() > 0
        log("Председатель: добавление члена", found, new_ln)
    except Exception as e:
        log("Председатель: добавление члена", False,
            f"{str(e)[:150]} | кнопки на странице: {describe_buttons(page)}")

    # 1.4 Список участков
    try:
        goto(page, "/plots")
        page.wait_for_selector(".q-page .q-list .q-item", timeout=TIMEOUT)
        count = row_count(page, "Нет участков")
        log("Председатель: список участков", count > 0, f"{count} строк")
    except Exception as e:
        log("Председатель: список участков", False, str(e)[:200])

    # 1.5 Поиск участка
    try:
        page.fill('input[placeholder*="Поиск"]', "1")
        page.wait_for_timeout(1200)
        count = row_count(page, "Нет участков")
        log("Председатель: поиск участка", count > 0, f"{count} результатов по «1»")
    except Exception as e:
        log("Председатель: поиск участка", False, str(e)[:200])

    # 1.6 Добавление участка. Номер случайный: у Plot стоит
    #     unique_together (organization, number), фиксированный номер
    #     упал бы при повторном прогоне без пересева.
    new_number = str(random.randint(9000, 9999))
    try:
        goto(page, "/plots")
        icon_btn(page, "add").first.click()
        page.wait_for_selector(".q-dialog", timeout=TIMEOUT)
        dialog_input(page, "Номер участка *").fill(new_number)
        dialog_input(page, "Площадь (соток)").fill("7.5")
        page.click('.q-dialog .q-btn:has-text("Сохранить")')
        page.wait_for_selector(".q-dialog", state="hidden", timeout=TIMEOUT)
        settle(page)
        page.fill('input[placeholder*="Поиск"]', new_number)
        page.wait_for_timeout(1200)
        found = page.locator(f'.q-item:has-text("{new_number}")').count() > 0
        log("Председатель: добавление участка", found, f"№{new_number}")
    except Exception as e:
        log("Председатель: добавление участка", False,
            f"{str(e)[:150]} | кнопки на странице: {describe_buttons(page)}")

    # 1.7 Начисления: вкладки
    try:
        goto(page, "/billing")
        page.wait_for_selector(".q-tab", timeout=TIMEOUT)
        tabs = page.locator(".q-tab").count()
        log("Председатель: страница начислений", tabs >= 3, f"{tabs} вкладки")
    except Exception as e:
        log("Председатель: страница начислений", False, str(e)[:200])

    for tab_name, empty_text in [("Долги", "Нет данных за период"),
                                 ("Начисления", "Нет начислений"),
                                 ("Платежи", "Нет платежей")]:
        try:
            page.click(f'.q-tab:has-text("{tab_name}")')
            settle(page)
            count = row_count(page, empty_text)
            log(f"Председатель: вкладка «{tab_name}»", True, f"{count} записей")
        except Exception as e:
            log(f"Председатель: вкладка «{tab_name}»", False, str(e)[:200])

    # 1.8 Электроэнергия
    try:
        goto(page, "/electricity")
        page.wait_for_selector(".q-tab", timeout=TIMEOUT)
        page.click('.q-tab:has-text("Счётчики")')
        settle(page)
        meters = row_count(page, "Нет счётчиков")
        page.click('.q-tab:has-text("Тарифы")')
        settle(page)
        tariffs = row_count(page, "Нет тарифов")
        log("Председатель: электроэнергия", meters > 0 and tariffs > 0,
            f"счётчиков: {meters}, тарифов: {tariffs}")
    except Exception as e:
        log("Председатель: электроэнергия", False, str(e)[:200])

    # 1.9 Отчёты
    try:
        url = goto(page, "/reports")
        ok = url.endswith("/reports")
        log("Председатель: страница отчётов", ok, url)
    except Exception as e:
        log("Председатель: страница отчётов", False, str(e)[:200])

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 2: КАЗНАЧЕЙ                                                         #
# =========================================================================== #

def story_treasurer(page: Page):
    print("\n" + "=" * 60)
    print("💰 РОЛЬ: КАЗНАЧЕЙ")
    print("=" * 60)

    try:
        login(page, TREASURER)
        log("Казначей: вход в систему", True)
    except Exception as e:
        log("Казначей: вход в систему", False, str(e)[:200])
        return

    try:
        settle(page)
        members = stat_value(page, "Членов")
        log("Казначей: дашборд", members.isdigit(), f"членов: {members}")
    except Exception as e:
        log("Казначей: дашборд", False, str(e)[:200])

    # 2.1 Доступ к реестру членов
    try:
        url = goto(page, "/members")
        ok = url.endswith("/members")
        log("Казначей: доступ к реестру членов", ok, url)
    except Exception as e:
        log("Казначей: доступ к реестру членов", False, str(e)[:200])

    # 2.2 Долги — профильная работа казначея
    try:
        goto(page, "/billing")
        page.click('.q-tab:has-text("Долги")')
        settle(page)
        count = row_count(page, "Нет данных за период")
        log("Казначей: ведомость долгов", count > 0, f"{count} записей")
    except Exception as e:
        log("Казначей: ведомость долгов", False, str(e)[:200])

    # 2.3 Массовое начисление — кнопки на вкладке долгов
    try:
        has_bulk = page.locator('.q-btn:has-text("Членский взнос")').count() > 0
        log("Казначей: кнопки массового начисления", has_bulk)
    except Exception as e:
        log("Казначей: кнопки массового начисления", False, str(e)[:200])

    # 2.4 Электроэнергия
    try:
        url = goto(page, "/electricity")
        ok = url.endswith("/electricity")
        log("Казначей: электроэнергия", ok, url)
    except Exception as e:
        log("Казначей: электроэнергия", False, str(e)[:200])

    # 2.5 Отчёты
    try:
        url = goto(page, "/reports")
        ok = url.endswith("/reports")
        log("Казначей: отчёты", ok, url)
    except Exception as e:
        log("Казначей: отчёты", False, str(e)[:200])

    # 2.6 Изоляция тенантов: чужие организации недоступны
    try:
        status = api_status(page, "/api/organizations/")
        ok = status in (403, 404)
        log("Казначей: /api/organizations/ закрыт", ok, f"HTTP {status}")
    except Exception as e:
        log("Казначей: /api/organizations/ закрыт", False, str(e)[:200])

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 3: ЧЛЕН СНТ                                                         #
# =========================================================================== #

def story_member(page: Page):
    print("\n" + "=" * 60)
    print("🏡 РОЛЬ: ЧЛЕН СНТ")
    print("=" * 60)

    try:
        login(page, MEMBER)
        log("Член СНТ: вход в систему", True)
    except Exception as e:
        log("Член СНТ: вход в систему", False, str(e)[:200])
        return

    # 3.1 Управленческая статистика скрыта
    try:
        settle(page)
        hidden = page.locator('.text-caption:text-is("Членов")').count() == 0
        log("Член СНТ: статистика управления скрыта", hidden,
            "" if hidden else "карточка «Членов» видна, а не должна")
    except Exception as e:
        log("Член СНТ: статистика управления скрыта", False, str(e)[:200])

    # 3.2 Разделы управления закрыты роутером (redirect на /dashboard)
    for path in ("/members", "/plots", "/billing", "/reports"):
        try:
            url = goto(page, path)
            ok = url.endswith("/dashboard")
            log(f"Член СНТ: {path} закрыт", ok, url)
        except Exception as e:
            log(f"Член СНТ: {path} закрыт", False, str(e)[:200])

    # 3.3 Показания счётчика — личный кабинет
    try:
        url = goto(page, "/meter-reading")
        on_page = url.endswith("/meter-reading")
        no_meter = page.locator(".bg-orange-1").count() > 0
        has_form = page.locator("form").count() > 0
        log("Член СНТ: страница показаний", on_page,
            "счётчик не привязан" if no_meter else ("форма доступна" if has_form else url))
    except Exception as e:
        log("Член СНТ: страница показаний", False, str(e)[:200])

    # 3.4 Передача показания
    try:
        if page.locator(".bg-orange-1").count() > 0:
            log("Член СНТ: передача показания", True, "нет счётчика — шаг неприменим")
        else:
            val = str(random.randint(9000, 9999))
            page.locator('.q-field:has(.q-field__label:text-is("Дата снятия показаний *")) input').fill(
                date.today().isoformat()
            )
            page.locator('.q-field:has(.q-field__label:text-is("Показание (кВт·ч) *")) input').fill(val)
            page.click('.q-btn:has-text("Передать показания")')
            settle(page)
            ok = page.locator(".q-notification--negative, .bg-negative").count() == 0
            log("Член СНТ: передача показания", ok, f"значение {val}")
    except Exception as e:
        log("Член СНТ: передача показания", False, str(e)[:200])

    logout(page)


# =========================================================================== #
#  ИСТОРИЯ 4: СУПЕРАДМИН                                                       #
# =========================================================================== #

def story_superadmin(page: Page):
    print("\n" + "=" * 60)
    print("🔑 РОЛЬ: СУПЕРАДМИН")
    print("=" * 60)

    try:
        login(page, SUPERADMIN)
        log("Суперадмин: вход в систему", True)
    except Exception as e:
        log("Суперадмин: вход в систему", False, str(e)[:200])
        return

    # 4.1 Видит все организации
    try:
        status = api_status(page, "/api/organizations/")
        log("Суперадмин: /api/organizations/ доступен", status == 200, f"HTTP {status}")
    except Exception as e:
        log("Суперадмин: /api/organizations/ доступен", False, str(e)[:200])

    # 4.2 Переключатель СНТ в шапке
    try:
        settle(page)
        switcher = page.locator('.q-chip:has(.q-icon:text-is("home_work")), '
                                '.q-btn:has-text("Выбрать СНТ")')
        log("Суперадмин: переключатель СНТ", switcher.count() > 0)
    except Exception as e:
        log("Суперадмин: переключатель СНТ", False, str(e)[:200])

    # 4.3 Django admin
    try:
        page.goto(f"{BASE_URL}/admin/")
        settle(page)
        ok = "admin" in page.url
        log("Суперадмин: Django admin", ok, page.url)
    except Exception as e:
        log("Суперадмин: Django admin", False, str(e)[:200])

    # 4.4 Swagger
    try:
        page.goto(f"{BASE_URL}/api/docs/")
        settle(page)
        body = page.locator("body").inner_text()
        ok = "swagger" in body.lower() or "openapi" in body.lower() or "API" in body
        log("Суперадмин: /api/docs/", ok)
    except Exception as e:
        log("Суперадмин: /api/docs/", False, str(e)[:200])


# =========================================================================== #
#  main                                                                        #
# =========================================================================== #

def main():
    print("\n🌱 SNT Платформа — Playwright тесты")
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
            viewport={"width": 390, "height": 844},   # iPhone 14 — mobile-first
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        )
        context.set_default_timeout(TIMEOUT)
        page = context.new_page()

        try:
            story_chairman(page)
            story_treasurer(page)
            story_member(page)
            story_superadmin(page)
        finally:
            context.close()
            browser.close()

    print("\n" + "=" * 60)
    print("📊 ИТОГ")
    print("=" * 60)
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
