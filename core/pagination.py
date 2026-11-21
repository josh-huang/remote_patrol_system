from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination; clients may ask for up to 500 rows per page."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 500
