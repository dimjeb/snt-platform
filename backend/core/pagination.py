from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Постраничная выдача с управляемым размером страницы.

    Без page_size_query_param DRF молча игнорирует ?page_size= из запроса.
    Фронт просил 100 начислений и 200 показаний, а получал всегда 50:
    на странице начислений больше полусотни записей не появлялось в
    принципе, а в выборе участка для счётчика — больше полусотни участков.
    Дашборд при этом тянул 50 сериализованных объектов, чтобы показать
    одно число из поля count.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
