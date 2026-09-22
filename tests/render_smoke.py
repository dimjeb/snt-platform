"""
Проверка, что страницы вне MainLayout вообще рисуются.

Белый экран фронтенд отдаёт молча: Vue ловит ошибку компонента, а
Quasar на QPage без QLayout над собой просто возвращает пустой рендер и
пишет одну строчку в консоль браузера. Ни один серверный тест этого не
видит — API отвечает 200, а человек смотрит в пустую страницу.

Здесь поднимается настоящий браузер и проверяется, что на странице
есть то, ради чего она существует.

Запуск — через scripts/check_browser.sh, он поднимает базу, Django и
раздачу собранного фронтенда.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8899")
LOGIN = os.environ["SMOKE_LOGIN"]
PASSWORD = os.environ["SMOKE_PASSWORD"]

ok, bad = 0, []


def verify(label, condition, extra=""):
    global ok
    if condition:
        ok += 1
        print(f"  ✅ {label} {extra}")
    else:
        bad.append(f"{label} {extra}".strip())
        print(f"  ❌ {label} {extra}")


def body_text(page):
    return (page.locator("body").inner_text() or "").strip()


def chromium_path():
    """
    Готовый Chromium, если он в системе уже есть.

    Версия playwright и версия скачанных браузеров могут разойтись, и
    тогда запуск требует `playwright install`. Там, где браузер
    установлен отдельно (например, в контейнере сборки), берём его
    напрямую — качать нечего.
    """
    import glob

    explicit = os.environ.get("SMOKE_CHROMIUM")
    if explicit:
        return explicit
    for pattern in (
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
    ):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


with sync_playwright() as pw:
    exe = chromium_path()
    browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 1. Страница входа
    page.goto(f"{BASE}/login", wait_until="networkidle")
    verify("страница входа не пустая", len(body_text(page)) > 40,
           f"символов {len(body_text(page))}")
    verify("на ней есть форма входа", page.locator("input").count() >= 2)

    # 2. Вход временным паролем уводит на смену пароля
    inputs = page.locator("input")
    inputs.nth(0).fill(LOGIN)
    inputs.nth(1).fill(PASSWORD)
    responses = []
    page.on("response", lambda r: responses.append((r.request.method, r.url, r.status)))
    page.get_by_role("button", name="Войти").click()
    try:
        page.wait_for_url("**/change-password", timeout=15000)
    except Exception:
        print("    URL сейчас:", page.url)
        print("    текст:", body_text(page)[:200].replace("\n", " | "))
        print("    запросы:")
        for method, url, status in responses[-8:]:
            print(f"      {method} {url} → {status}")
        print("    ошибки консоли:", errors[:5])
        raise
    page.wait_for_load_state("networkidle")

    text = body_text(page)
    verify("страница смены пароля не пустая", len(text) > 40,
           f"символов {len(text)}")
    verify("на ней есть заголовок", "Смена пароля" in text)
    verify("видно, что пароль временный", "временный" in text.lower())
    verify("есть три поля ввода", page.locator("input").count() >= 3,
           f"полей {page.locator('input').count()}")
    verify("есть кнопка сохранения",
           page.get_by_role("button", name="Сохранить").count() > 0)

    # 3. Прямой заход по адресу — тот самый случай с белым экраном
    page.goto(f"{BASE}/change-password", wait_until="networkidle")
    text = body_text(page)
    verify("прямой заход на /change-password не даёт белый экран",
           "Смена пароля" in text, f"символов {len(text)}")

    # 4. Ошибки в консоли — именно так белый экран себя и проявлял
    layout_errors = [e for e in errors if "QPage" in e or "QLayout" in e]
    verify("нет жалоб Quasar на layout", not layout_errors,
           "; ".join(layout_errors[:2]))

    browser.close()

print()
print(f"Проверок: {ok + len(bad)}, прошло {ok}, упало {len(bad)}")
if bad:
    print("\nПровалившиеся:")
    for b in bad:
        print(f"  • {b}")
    sys.exit(1)
print("Страницы рисуются.")
