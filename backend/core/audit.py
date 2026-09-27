"""
Регистрация обращений к персональным данным.

Пишем только удачные чтения: неудачную попытку логировать незачем —
данные не ушли, а поток мусора в журнале мешает разбирать настоящие
обращения.
"""
import logging

from .logging import scrub
from .models import AccessLog

log = logging.getLogger(__name__)


def client_ip(request):
    """
    IP клиента с учётом обратного прокси.

    Caddy проксирует в Django по http, поэтому REMOTE_ADDR — это всегда
    адрес контейнера Caddy. Настоящий адрес приходит в X-Forwarded-For,
    первым в цепочке.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record_access(request, resource, action, object_id="", records=0):
    """
    Записать обращение. Никогда не роняет сам запрос.

    Сбой аудита не должен превращаться в 500 для пользователя: данные он
    уже получил, и отказ на этом этапе ничего не защитит. Но и молчать
    нельзя — пишем в журнал приложения с уровнем error, чтобы пропажа
    записей была заметна.
    """
    try:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return
        AccessLog.objects.create(
            user=user,
            username=user.get_username(),
            organization=getattr(request, "org", None),
            resource=resource,
            action=action,
            object_id=str(object_id or "")[:50],
            records=records or 0,
            ip=client_ip(request),
            # Путь чистим тем же фильтром: в ?search= лежит ФИО, а журнал
            # доступа не должен сам стать хранилищем ПДн.
            path=scrub(request.get_full_path())[:255],
        )
    except Exception:
        log.exception("Не удалось записать обращение к ПДн: %s/%s", resource, action)


def _count_records(data):
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return len(data["results"])
        return 1
    if isinstance(data, list):
        return len(data)
    return 0


class AccessLoggedMixin:
    """
    Пишет в журнал успешные чтения вьюсета.

    Вешается на finalize_response, а не на list/retrieve: так запись
    появляется только когда ответ действительно сформирован, и не надо
    дублировать вызов в каждом методе.
    """

    audit_resource = ""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if not self.audit_resource:
            return response
        if request.method != "GET" or not (200 <= response.status_code < 300):
            return response
        action = AccessLog.ACTION_DETAIL if kwargs.get("pk") else AccessLog.ACTION_LIST
        record_access(
            request, self.audit_resource, action,
            object_id=kwargs.get("pk", ""),
            records=_count_records(getattr(response, "data", None)),
        )
        return response
