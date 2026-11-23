from rest_framework.pagination import PageNumberPagination
from rest_framework.utils.urls import remove_query_param, replace_query_param


class EventPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def links(self, request, page, size, count):
        """next/previous links, built per request so a cached page never leaks another request's URL."""
        url = request.build_absolute_uri()
        next_url = (
            replace_query_param(url, self.page_query_param, page + 1)
            if page * size < count
            else None
        )
        if page <= 1:
            previous_url = None
        elif page == 2:
            previous_url = remove_query_param(url, self.page_query_param)
        else:
            previous_url = replace_query_param(url, self.page_query_param, page - 1)
        return next_url, previous_url