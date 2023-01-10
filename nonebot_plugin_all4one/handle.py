from .data import Data
from .parser import Namespace


class Handle:
    @classmethod
    def sc(cls, args: Namespace):
        return cls.subcommand(args)

    @classmethod
    def subcommand(cls, args: Namespace):
        pass
