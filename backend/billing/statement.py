"""
Разбор банковской выписки в формате «1С:Клиент-Банк».

Этот формат отдают все основные банки — Сбер, ВТБ, Т-Банк, Альфа, — и он
единственный, на который можно опираться: выгрузка в Excel у каждого
банка своя и меняется без предупреждения, а `1CClientBankExchange`
описан и стабилен много лет.

Устройство файла: построчно «Ключ=Значение», документы обёрнуты в
СекцияДокумент ... КонецДокумента. Кодировка обычно windows-1251,
изредка UTF-8.

    1CClientBankExchange
    ВерсияФормата=1.03
    Кодировка=Windows
    РасчСчет=40703810100810020382
    СекцияДокумент=Платежное поручение
    Номер=123
    Дата=15.09.2026
    Сумма=3059.30
    Плательщик=ЖЕБРОВСКИЙ ДМИТРИЙ СЕРГЕЕВИЧ
    ПолучательСчет=40703810100810020382
    НазначениеПлатежа=Участок 88. ТСН "Здоровье"
    КонецДокумента
    КонецФайла
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MARKER = "1CClientBankExchange"


class StatementError(Exception):
    """Файл не похож на выписку или повреждён."""


@dataclass
class StatementDocument:
    """Одна строка выписки."""
    number: str = ""
    doc_date: date | None = None
    amount: Decimal = Decimal("0")
    payer_name: str = ""
    payer_account: str = ""
    payer_inn: str = ""
    payee_account: str = ""
    purpose: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def is_incoming_for(self):
        """Функция-предикат создаётся вызывающим кодом: см. parse_1c_statement."""
        raise NotImplementedError


@dataclass
class ParsedStatement:
    account: str = ""
    date_from: date | None = None
    date_to: date | None = None
    sender: str = ""
    documents: list = field(default_factory=list)


def _decode(raw: bytes) -> str:
    """
    Привести файл к тексту.

    Кодировка объявлена внутри файла, но чтобы её прочитать, файл уже
    надо декодировать. Поэтому идём от обратного: пробуем UTF-8 строго,
    и если байты ему не соответствуют — это windows-1251. Русский текст
    в 1251 почти никогда не оказывается валидным UTF-8, так что различие
    надёжное.
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("windows-1251", errors="replace")


def _parse_date(value: str):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> Decimal:
    cleaned = re.sub(r"[^\d,.\-]", "", value or "").replace(",", ".")
    # Разделители тысяч банк иногда ставит точкой: берём последнюю точку
    # как десятичную, остальные убираем.
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    try:
        return Decimal(cleaned or "0")
    except InvalidOperation:
        return Decimal("0")


def parse_1c_statement(raw: bytes, *, our_account: str = "") -> ParsedStatement:
    """
    Разобрать файл выписки.

    our_account — расчётный счёт товарищества. Он нужен, чтобы отличить
    приход от расхода: в выписке есть и то и другое, а разносить по
    начислениям надо только поступления.
    """
    text = _decode(raw)
    if MARKER not in text:
        raise StatementError(
            "Это не выписка в формате «1С:Клиент-Банк». Выгрузите из "
            "банк-клиента обмен с 1С — обычно файл называется kl_to_1c.txt."
        )

    result = ParsedStatement()
    current = None
    in_document = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("СекцияДокумент"):
            current = {}
            in_document = True
            continue
        if line.startswith("КонецДокумента"):
            if current is not None:
                doc = _build_document(current)
                if doc is not None:
                    result.documents.append(doc)
            current, in_document = None, False
            continue
        if line.startswith(("СекцияРасчСчет", "КонецРасчСчет", "КонецФайла")):
            continue

        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()

        if in_document and current is not None:
            # Многострочное назначение платежа банки пишут повтором ключа.
            if key in current and key == "НазначениеПлатежа":
                current[key] = f"{current[key]} {value}".strip()
            else:
                current[key] = value
            continue

        # Шапка файла
        if key == "РасчСчет" and not result.account:
            result.account = value
        elif key == "ДатаНачала":
            result.date_from = _parse_date(value)
        elif key == "ДатаКонца":
            result.date_to = _parse_date(value)
        elif key == "Отправитель":
            result.sender = value

    if our_account:
        account = re.sub(r"\D", "", our_account)
        result.documents = [
            d for d in result.documents
            if re.sub(r"\D", "", d.payee_account) == account
        ]
    return result


def _build_document(data: dict):
    doc = StatementDocument(
        number=data.get("Номер", ""),
        doc_date=_parse_date(data.get("Дата", "")),
        amount=_parse_amount(data.get("Сумма", "")),
        payer_name=data.get("Плательщик", "").strip(),
        payer_account=data.get("ПлательщикСчет", "")
        or data.get("ПлательщикРасчСчет", ""),
        payer_inn=data.get("ПлательщикИНН", ""),
        payee_account=data.get("ПолучательСчет", "")
        or data.get("ПолучательРасчСчет", ""),
        purpose=data.get("НазначениеПлатежа", "").strip(),
        raw=data,
    )
    if doc.amount <= 0 or doc.doc_date is None:
        # Строка без суммы или без даты — это не платёж, а мусор разметки.
        return None
    return doc
