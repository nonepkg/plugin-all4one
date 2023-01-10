import argparse
from argparse import Namespace as BaseNamespace

from nonebot.rule import ArgumentParser


class Namespace(BaseNamespace):
    pass


parser = ArgumentParser("command")

subparsers = parser.add_subparsers(dest="handle")

subcommand_parent = subparsers.add_parser(
    "subcommand_parent", help="Subcommand example", add_help=False
)
subparsers.add_parser("subcommand", parents=[subcommand_parent])
subparsers.add_parser("sc", parents=[subcommand_parent])
