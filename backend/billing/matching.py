"""
Сопоставление строк выписки с участками и членами товарищества.

Задача: по назначению платежа и имени плательщика понять, чей это
перевод. Ошибка здесь — это чужой долг, закрытый чужими деньгами,
поэтому уверенное сопоставление и догадка разделены явно: догадку
казначей подтверждает руками.
"""
import re
import unicodedata

# Номер участка в назначении платежа. Порядок важен: сначала явные
# формулировки, потом общие — иначе «оплата по счёту №12 за участок 88»
# опознается как участок 12.
# Номер участка: обычно цифры, но бывают «12а» и «а-15» — в больших
# товариществах номера с буквенным префиксом по улицам. Допускаем до
# трёх букв перед цифрами, но только слитно или через дефис: иначе
# «участок за 2026» опознался бы как участок «за 2026».
NUMBER = r"([а-яa-z]{0,3}-?[0-9]+[а-яa-z]?)"

PLOT_PATTERNS = [
    # Падежные формы перечислены явно, а не «участ[а-я]*»: иначе под
    # шаблон попадает «участник», и «участник 5» стал бы участком 5.
    r"участ(?:ок|ка|ке|ку|ком|ки|ках|кам)\s*" + NUMBER,
    r"уч[\.\s]\s*" + NUMBER,
    r"л\s*[/\.]?\s*с\s*" + NUMBER,
    r"лицев[а-я]*\s*счет[а-я]*\s*" + NUMBER,
    # Номер перед словом: «целевой взнос 57 уч», «взнос 88 участок».
    # Идёт последним, чтобы явные формы («уч. 80») выигрывали.
    # Цифр не больше трёх и обязательна граница слова перед номером:
    # иначе «взнос на 2027 уч» дал бы участок «027». Участки с
    # четырёхзначными номерами в такой записи не опознаются — в этом
    # случае номер от года не отличить, и лучше отдать строку казначею.
    r"\b([а-яa-z]{0,3}-?[0-9]{1,3}[а-яa-z]?)\s*"
    r"(?:уч\b|участ(?:ок|ка|ке|ку)\b)",
]

# Насколько уверены в сопоставлении
MATCH_PLOT = "plot"        # номер участка найден в назначении — надёжно
MATCH_NAME = "name"        # опознали по ФИО плательщика — предположение
MATCH_NONE = "none"        # не опознали


def _normalize(text: str) -> str:
    # Знак № выкидываем ДО нормализации. NFKC раскладывает его в «no»,
    # и шаблоны с «№» переставали срабатывать на «участок №88» — поймано
    # прогоном, не рассуждением. Смысла он не несёт: цифры идут следом.
    text = (text or "").replace("№", " ")
    text = unicodedata.normalize("NFKC", text).lower()
    # Ё и е в банковских выписках встречаются вперемешку.
    return text.replace("ё", "е")


def extract_plot_number(purpose: str):
    """Достать номер участка из назначения платежа."""
    text = _normalize(purpose)
    for pattern in PLOT_PATTERNS:
        found = re.search(pattern, text)
        if found:
            return found.group(1).strip()
    return None


# Категория платежа по назначению. Корни, а не слова целиком: банки и
# люди пишут «ЦЕЛЕВОЙ», «целевого», «Целевые взносы», «членск. взнос».
CATEGORY_PATTERNS = {
    "membership": r"членск",
    "target": r"целев",
    # «эл.энергия», «электроэнергия», «за свет», «кВт»
    "electricity": r"электр|эл\.?\s*энерг|за\s+свет|\bсвет\b|квт",
}


def extract_category(purpose: str) -> str:
    """
    На что платили, если это видно из назначения: membership / target /
    electricity. Пустая строка, если категория не названа — или названо
    сразу несколько («членский и целевой взнос»): тогда угадывать нельзя,
    деньги разносятся как обычно, от старых начислений к новым.
    """
    text = _normalize(purpose)
    found = [name for name, pattern in CATEGORY_PATTERNS.items()
             if re.search(pattern, text)]
    return found[0] if len(found) == 1 else ""


def _name_key(text: str):
    """
    Ключ для сравнения ФИО: фамилия и первые буквы имени и отчества.

    Банк присылает «ЖЕБРОВСКИЙ ДМИТРИЙ СЕРГЕЕВИЧ», в реестре может быть
    «Жебровский Дмитрий Сергеевич» или сокращённо. Сравниваем по
    фамилии плюс инициалы — этого достаточно, чтобы различить однофамильцев
    с разными именами, и устойчиво к сокращениям.
    """
    parts = [p for p in re.split(r"[\s.]+", _normalize(text)) if p]
    if not parts:
        return None
    last = parts[0]
    initials = "".join(p[0] for p in parts[1:3])
    return (last, initials)


def match_documents(documents, *, plots, members):
    """
    Сопоставить строки выписки.

    plots   — словарь {нормализованный номер участка: Plot}
    members — список Member (с подтянутыми ownerships)

    Возвращает список кортежей (документ, участок|None, член|None, уверенность).
    """
    by_name = {}
    for member in members:
        key = _name_key(member.full_name)
        if key is None:
            continue
        # Однофамильцев с одинаковыми инициалами по имени не различить —
        # такие вообще не сопоставляем, пусть казначей решает сам.
        by_name.setdefault(key, []).append(member)

    results = []
    for doc in documents:
        number = extract_plot_number(doc.purpose)
        plot = plots.get(_normalize(number)) if number else None
        if plot is not None:
            owner = next(iter(plot.current_owners), None)
            results.append((doc, plot, owner, MATCH_PLOT))
            continue

        key = _name_key(doc.payer_name)
        candidates = by_name.get(key, []) if key else []
        if len(candidates) == 1:
            member = candidates[0]
            member_plots = member.plots
            # По имени сопоставляем только когда участок единственный:
            # иначе непонятно, за какой из них платили.
            plot = member_plots[0] if len(member_plots) == 1 else None
            results.append((doc, plot, member, MATCH_NAME))
            continue

        results.append((doc, None, None, MATCH_NONE))
    return results
