from nonebot.typing import T_State
from nonebot.adapters import Bot, Event
from nonebot.plugin import on_shell_command

from .data import Data
from .handle import Handle
from .parser import Namespace, parser

command = on_shell_command("command", parser=parser, priority=1)


@command.handle()
async def _(bot: Bot, event: Event, state: T_State):

    args: Namespace = state["args"]

    if hasattr(args, "handle"):
        try:
            await bot.send(event, getattr(Handle, args.handle)(args))
        except:
            pass
    else:
        await bot.send(event, args.message)
