from dataclasses import dataclass


@dataclass
class PaginationRequest:
    page: int
    per_page: int
    query: str


@dataclass
class PaginationResponse:
    page: int
    per_page: int
    total: int
    data: list

    @property
    def count(self):
        return len(self.data)
