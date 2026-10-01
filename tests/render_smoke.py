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

    # 1a. Инструкция доступна до входа — со страницы логина.
    #     Человеку с бумажкой чаще непонятно не как нажать «Войти», а что
    #     делать дальше, поэтому ссылка обязана быть именно здесь.
    link = page.get_by_role("link", name="Инструкция: как пользоваться сайтом")
    verify("на странице входа есть ссылка на инструкцию", link.count() > 0)
    if link.count():
        link.first.click()
        page.wait_for_url("**/help", timeout=15000)
        page.wait_for_load_state("networkidle")
        help_text = body_text(page)
        verify("инструкция открывается без входа", len(help_text) > 2000,
               f"символов {len(help_text)}")
        verify("в ней есть истории «Хочу…»",
               "Хочу узнать, сколько я должен" in help_text)
        verify("есть раздел казначея", "Я казначей" in help_text)
        # Инструкция вшивается в бандл на сборке (?raw-импорт файла), а не
        # читается с диска на лету. Значит, правку текста легко забыть
        # выкатить: в репозитории раздел есть, а на сайте старая версия.
        # Проверяем свежие разделы поимённо.
        verify("на сайте описан расчёт по соткам",
               "Ставка за сотку" in help_text)
        verify("на сайте описан взнос «за члена»",
               "За члена товарищества" in help_text)
        verify("на сайте описан перенос оплаты",
               "Хочу перенести оплату" in help_text)
        verify("на сайте описаны пени за просрочку",
               "Хочу начислить пени за просрочку" in help_text
               and "не задвоятся" in help_text)
        verify("разметка отрисована, а не показан сырой текст",
               "##" not in help_text and page.locator("h2").count() > 3,
               f"заголовков h2: {page.locator('h2').count()}")
        # Оглавление ссылается на «#я-садовод» — идентификаторы должны
        # проставляться, иначе переходы из оглавления никуда не ведут.
        verify("у заголовков есть якоря для оглавления",
               page.locator("#я-садовод").count() > 0)
        verify("предупреждения оформлены заметно",
               page.locator("blockquote").count() > 5,
               f"цитат: {page.locator('blockquote').count()}")
        page.goto(f"{BASE}/login", wait_until="networkidle")

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

    # 4. Сама смена пароля проходит и пускает в кабинет
    new_password = PASSWORD + "-Xq7"
    fields = page.locator("input")
    fields.nth(0).fill(PASSWORD)
    fields.nth(1).fill(new_password)
    fields.nth(2).fill(new_password)
    page.get_by_role("button", name="Сохранить").click()
    try:
        page.wait_for_url("**/dashboard", timeout=15000)
    except Exception:
        print("    URL сейчас:", page.url)
        print("    текст:", body_text(page)[:200].replace("\n", " | "))
        raise
    page.wait_for_load_state("networkidle")

    text = body_text(page)
    verify("после смены пароля открывается кабинет", len(text) > 40,
           f"символов {len(text)}")

    # Долг приезжает отдельным запросом уже после загрузки страницы:
    # networkidle его не дожидается, и читать текст сразу — значит
    # мерить полупустой экран.
    try:
        page.wait_for_function(
            "() => document.body.innerText.includes('15')", timeout=10000,
        )
        shown = True
    except Exception:
        shown = False
    verify("в кабинете виден долг", shown, body_text(page)[:150])

    verify("в меню приложения есть пункт «Инструкция»",
           "Инструкция" in text, "")

    # 5. Диалог оплаты по QR. Комиссию берёт банк плательщика, а не
    #    товарищество, и об этом должно быть сказано прямо в диалоге:
    #    человек, впервые увидевший её при оплате, идёт звонить казначею.
    page.get_by_role("button", name="Оплатить по QR из банка").click()
    page.wait_for_timeout(2500)
    dialog = body_text(page)
    verify("диалог QR открывается", "Оплата по QR" in dialog)
    verify("в диалоге есть сам QR", page.locator("img[alt*='QR']").count() > 0)
    verify("сказано, что комиссию может взять банк",
           "комисси" in dialog.lower(),
           "" if "комисси" in dialog.lower() else dialog[:200])
    verify("сказано, что она не относится к товариществу",
           "не относится к товариществу" in dialog)

    # 4. Ошибки в консоли — именно так белый экран себя и проявлял
    layout_errors = [e for e in errors if "QPage" in e or "QLayout" in e]
    verify("нет жалоб Quasar на layout", not layout_errors,
           "; ".join(layout_errors[:2]))

    # 6. Председатель выдаёт доступ кнопкой и видит пароль один раз.
    page.goto(f"{BASE}/login", wait_until="networkidle")
    fields = page.locator("input")
    fields.nth(0).fill(LOGIN + "-chair")
    fields.nth(1).fill(PASSWORD)
    page.get_by_role("button", name="Войти").click()
    page.wait_for_url("**/dashboard", timeout=15000)

    page.goto(f"{BASE}/members", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.get_by_text("Бездоступов").first.click()
    page.wait_for_timeout(800)
    card = body_text(page)
    verify("в карточке видно, что доступ не выдан", "Доступ не выдан" in card,
           card[:150])

    page.get_by_role("button", name="Выдать доступ").click()
    page.wait_for_timeout(2500)
    issued = body_text(page)
    verify("окно с паролем открылось", "Доступ выдан" in issued, issued[:150])
    verify("логин показан", "bezdostupov" in issued.lower(), "")
    # Пароль вида xxxx-xxxx-xxxx из алфавита без похожих символов
    import re as _re
    verify("временный пароль показан",
           bool(_re.search(r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", issued)), "")
    verify("сказано, что второй раз пароль не покажут",
           "Повторно пароль показать нельзя" in issued, "")

    # 7. Пени: кнопка начисляет и расшифровка видна на вкладке
    #    «Начисления». Отчёт пользователя был именно про это — пени
    #    появились, а за что они, на экране не нашлось.
    page.goto(f"{BASE}/billing", wait_until="networkidle")
    page.wait_for_timeout(2000)

    # Имя собственника в сводке долгов: шаблон читал несуществующее
    # поле member_name, и во всех строках стоял голый номер участка с
    # висящим тире. Серверный тест этого не видит — API отвечал верно.
    debt_text = body_text(page)
    verify("в сводке долгов видно имя собственника",
           "Проверкин" in debt_text, debt_text[:200])

    page.get_by_role("button", name="Начислить пени").click()
    page.wait_for_timeout(800)
    confirm = body_text(page)
    verify("перед начислением пеней спрашивают подтверждение",
           "от остатка долга" in confirm, confirm[:160])
    page.get_by_role("button", name="Начислить", exact=True).click()
    page.wait_for_timeout(2500)
    verify("пени начислены кнопкой",
           "Начислено пеней" in body_text(page), body_text(page)[:160])

    page.get_by_role("tab", name="Начисления").click()
    page.wait_for_timeout(1500)
    charges_text = body_text(page)
    verify("в списке появилась строка пеней",
           "Пени за просрочку" in charges_text, charges_text[:200])
    verify("расшифровка пеней видна: ставка, срок и долг",
           "Пени 20 % за просрочку" in charges_text
           and "срок 01.09.2026" in charges_text,
           charges_text[:300])
    verify("у просроченного начисления виден срок оплаты",
           "Оплатить до 01.09.2026" in charges_text, "")

    # Порядок строк: номера участков по числу, а не по буквам, и пени
    # сразу под тем начислением, за просрочку которого выписаны.
    pos2 = charges_text.find("Уч. №2 ")
    pos10 = charges_text.find("Уч. №10 ")
    verify("участок 2 стоит раньше участка 10",
           0 <= pos2 < pos10, f"позиции {pos2} и {pos10}")
    parent = charges_text.find("Оплатить до 01.09.2026")
    penalty = charges_text.find("срок 01.09.2026")
    between = charges_text[parent:penalty] if 0 <= parent < penalty else ""
    verify("пени стоят сразу под своим начислением",
           0 <= parent < penalty and "Уч. №2 " not in between
           and "Целевой взнос" not in between,
           f"позиции {parent} и {penalty}")

    # 8. Перенос оплаты через интерфейс: с оплаченного целевого участка 2
    #    на его же членский.
    transfer_buttons = page.get_by_role("button", name="Перенести оплату")
    verify("у оплаченного начисления есть кнопка переноса",
           transfer_buttons.count() >= 1, f"кнопок {transfer_buttons.count()}")
    if transfer_buttons.count():
        transfer_buttons.first.click()
        page.wait_for_timeout(1500)
        page.get_by_label("На начисление *").click()
        page.wait_for_timeout(600)
        page.get_by_role("option").first.click()
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Перенести", exact=True).click()
        page.wait_for_timeout(2500)
        verify("перенос оплаты проходит из интерфейса",
               "Перенесено" in body_text(page), body_text(page)[:200])
        page.get_by_role("tab", name="Платежи").click()
        page.wait_for_timeout(1200)
        verify("перенос виден в платежах парой строк",
               body_text(page).count("Перенос между начислениями") == 2,
               f"строк {body_text(page).count('Перенос между начислениями')}")

    # 8б. Срок оплаты у уже созданных начислений — разом всем участкам.
    page.get_by_role("tab", name="Долги").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Срок оплаты").click()
    page.wait_for_timeout(800)
    page.get_by_label("Вид начисления *").click()
    page.wait_for_timeout(400)
    page.get_by_role("option", name="Членский взнос").click()
    page.wait_for_timeout(300)
    page.get_by_label("Оплатить до").fill("2027-07-15")
    page.get_by_role("button", name="Изменить срок").click()
    page.wait_for_timeout(2000)
    due_text = body_text(page)
    verify("срок оплаты меняется из интерфейса",
           "Срок изменён у" in due_text,
           due_text[due_text.find("Срок"):][:160] if "Срок" in due_text else "")
    verify("сказано про пени за просрочку, которой больше нет",
           "уже начислены пени" in due_text, "")

    # 9. Разделение одного платежа выписки по категориям с суммами.
    page.goto(f"{BASE}/statements", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.get_by_text("split-check.xlsx").first.click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Разделить по категориям").first.click()
    page.wait_for_timeout(800)
    amounts = page.get_by_label("Сумма", exact=True)
    # По умолчанию — распознанная категория на всю сумму платежа.
    verify("в разделении подставлена распознанная категория на всю сумму",
           amounts.count() == 1 and amounts.nth(0).input_value() == "1000.00"
           and "Членский взнос" in page.locator(".q-dialog").inner_text(),
           f"строк {amounts.count()}, сумма {amounts.nth(0).input_value() if amounts.count() else '—'}")
    amounts.nth(0).fill("600")
    page.wait_for_timeout(200)
    # «Ещё категория» — следующая невыбранная и остаток.
    page.get_by_role("button", name="Ещё категория").click()
    page.wait_for_timeout(300)
    verify("вторая часть подставилась сама: целевой и остаток 400",
           amounts.count() == 2 and amounts.nth(1).input_value() == "400",
           f"вторая сумма {amounts.nth(1).input_value() if amounts.count() > 1 else '—'}")
    verify("подсказка показывает, что разделено полностью",
           "Разделено полностью" in body_text(page), "")
    page.get_by_role("button", name="Сохранить").click()
    page.wait_for_timeout(1500)
    split_text = body_text(page)
    verify("разделение сохранилось и видно в строке выписки",
           "Разделено: Членский взнос 600,00 ₽ + Целевой взнос 400,00 ₽" in split_text,
           split_text[split_text.find("Разделено"):][:120] if "Разделено" in split_text else "строки нет")

    browser.close()

print()
print(f"Проверок: {ok + len(bad)}, прошло {ok}, упало {len(bad)}")
if bad:
    print("\nПровалившиеся:")
    for b in bad:
        print(f"  • {b}")
    sys.exit(1)
print("Страницы рисуются.")
