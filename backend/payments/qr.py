"""
Платёжный QR-код по ГОСТ Р 56042-2014.

Это тот самый QR, что печатают в квитанциях ЖКХ: человек наводит камеру
в приложении своего банка, реквизиты и сумма подставляются сами, он
подтверждает перевод. Ни эквайринга, ни кассы для этого не нужно —
деньги идут обычным переводом на расчётный счёт товарищества, и
комиссию товарищество не платит.

Формат строки:

    ST00012|Name=...|PersonalAcc=...|BankName=...|BIC=...|CorrespAcc=...|<доп. поля>

    ST      идентификатор формата
    0001    версия
    2       кодировка UTF-8

Первые пять полей обязательны и идут строго в этом порядке. Остальные —
в любом. Сумма передаётся В КОПЕЙКАХ целым числом.
"""
from decimal import Decimal, ROUND_HALF_UP

SERVICE_ID = "ST00012"
SEPARATOR = "|"

# Практический предел длины. Сам QR вмещает килобайты, но чем плотнее
# картинка, тем хуже она читается с экрана телефона под углом.
# Реальные квитанции ЖКХ несут 300–400 байт, поэтому 512 — запас с
# двойным хвостом. Ровно 300, как я прикидывал сначала, не годится:
# одни только обязательные реквизитыc длинным наименованием банка и
# полным названием товарищества занимают больше.
MAX_PAYLOAD = 512


class QRError(Exception):
    """Не хватает данных, чтобы построить платёжный QR."""


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _trim_to_bytes(text: str, limit: int) -> str:
    """Обрезать строку так, чтобы она заняла не больше limit байт."""
    if limit <= 0:
        return ""
    encoded = text.encode("utf-8")[:limit]
    # Хвост мог обрубиться посреди многобайтового символа.
    return encoded.decode("utf-8", errors="ignore")


def _clean(value) -> str:
    """
    Убирает из значения разделитель и переносы строк.

    Вертикальная черта разделяет поля: попав внутрь значения, она
    сдвинет всю разметку, и банк прочитает реквизиты неправильно.
    """
    text = str(value or "")
    for bad in ("|", "\n", "\r", "\t"):
        text = text.replace(bad, " ")
    return " ".join(text.split())


def build_payment_payload(organization, *, amount=None, purpose="", pers_acc=""):
    """
    Собирает строку платёжного QR для организации.

    amount   — сумма в рублях (Decimal). None — банк спросит сумму сам.
    purpose  — назначение платежа.
    pers_acc — лицевой счёт плательщика; сюда кладём номер участка, по
               нему казначей потом опознаёт платёж в выписке.
    """
    if not organization.has_bank_details:
        raise QRError(
            "У организации не заполнены банковские реквизиты: нужны "
            "полное наименование, расчётный счёт, банк, БИК и "
            "корреспондентский счёт."
        )

    # Порядок первых пяти полей задан стандартом и менять его нельзя.
    parts = [
        SERVICE_ID,
        f"Name={_clean(organization.payment_name)}",
        f"PersonalAcc={_clean(organization.bank_account)}",
        f"BankName={_clean(organization.bank_name)}",
        f"BIC={_clean(organization.bank_bic)}",
        f"CorrespAcc={_clean(organization.bank_corr_account)}",
    ]

    if organization.inn:
        parts.append(f"PayeeINN={_clean(organization.inn)}")
    if organization.kpp:
        parts.append(f"KPP={_clean(organization.kpp)}")

    if amount is not None:
        kopecks = (Decimal(amount) * 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        if kopecks <= 0:
            raise QRError("Сумма платежа должна быть больше нуля.")
        parts.append(f"Sum={int(kopecks)}")

    if pers_acc:
        # Лицевой счёт банк показывает плательщику и переносит в
        # назначение — это самая надёжная зацепка для сверки.
        parts.append(f"PersAcc={_clean(pers_acc)}")
    if purpose:
        parts.append(f"Purpose={_clean(purpose)}")

    payload = SEPARATOR.join(parts)
    if _size(payload) <= MAX_PAYLOAD:
        return payload

    # Слишком длинно. Режем назначение — без него платёж дойдёт, без
    # верного счёта нет. Считаем в байтах и режем по символам, иначе на
    # кириллице промахиваешься вдвое: один символ здесь два байта.
    if purpose:
        without_purpose = SEPARATOR.join(parts[:-1])
        room = MAX_PAYLOAD - _size(without_purpose) - _size(SEPARATOR + "Purpose=")
        trimmed = _trim_to_bytes(_clean(purpose), room)
        if trimmed:
            parts[-1] = f"Purpose={trimmed}"
        else:
            parts = parts[:-1]
        payload = SEPARATOR.join(parts)
        if _size(payload) <= MAX_PAYLOAD:
            return payload

    # Даже без назначения не влезаем — виноваты сами реквизиты. Молча
    # отдавать обрезанный QR нельзя: он уведёт деньги не туда.
    raise QRError(
        f"Реквизиты не помещаются в QR-код ({_size(payload)} байт при "
        f"пределе {MAX_PAYLOAD}). Обычно виновато слишком длинное "
        f"наименование банка или организации — сократите его."
    )


def build_purpose(organization, *, plot_numbers, period_label=""):
    """
    Назначение платежа.

    Номер участка здесь обязателен: по выписке казначей опознаёт платёж
    именно по нему. ФИО не пишем — оно и так приедет из банка
    плательщика, а лишний раз гонять персональные данные незачем.
    """
    plots = ", ".join(str(n) for n in plot_numbers if n)
    text = f"Участок {plots}" if plots else "Взносы"
    if period_label:
        text += f", {period_label}"
    text += f". {organization.name}"
    return _clean(text)


# Минимальный размер картинки на экране. Замеряно: строка нашей длины
# при коррекции Q перестаёт распознаваться где-то ниже 240 px, поэтому
# 300 — с запасом. Показывать QR мельче нельзя, его просто не считают.
MIN_DISPLAY_PX = 300
TARGET_PX = 640


def render_png(payload: str) -> bytes:
    """
    QR как PNG. Вынесено отдельно от сборки строки: строку можно
    проверить и без картинки, а картинку — без обращения к базе.

    Коррекция Q, а не M, хотя модулей от неё больше. Это проверено
    замером, а не выбрано по наитию: на уменьшенной картинке (а именно
    так QR и выглядит на экране телефона) избыточность Q отыгрывает
    потери при масштабировании, и код читается с 240 px, тогда как
    M и L — только с 280.
    """
    import io

    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q,
                       border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    # Подгоняем модуль так, чтобы картинка вышла около TARGET_PX: мелкая
    # плохо читается, гигантская зря весит.
    modules = qr.modules_count + qr.border * 2
    qr.box_size = max(4, round(TARGET_PX / modules))

    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()
