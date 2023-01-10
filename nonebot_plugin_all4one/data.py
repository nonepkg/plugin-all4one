import json
from pathlib import Path


class Data:
    __path: Path
    __data: dict
    __data_template: dict = {}

    def __init__(
        self,
        path: Path = Path() / "data" / "all4one" / "config.yml",
    ):
        self.__path = path
        self.__load()

    def get(self):
        pass

    def update(self):
        pass

    def add(self):
        pass

    def remove(self):
        pass

    def __load(self) -> "Data":
        try:
            self.__data = safe_load(self.__path.open("r", encoding="utf-8"))
        except FileNotFoundError:
            self.__data = self.__data_template
        return self

    def __dump(self):
        self.__path.parent.mkdir(parents=True, exist_ok=True)
        dump(
            self.__data,
            self.__path.open("w", encoding="utf-8"),
            allow_unicode=True,
        )
