import pytest
import nonebot
from nonebug import NONEBOT_INIT_KWARGS
from nonebot.adapters.console import Adapter as ConsoleAdapter
from nonebot.adapters.qqguild import Adapter as QQGuildAdapter
from nonebot.adapters.telegram import Adapter as TelegramAdapter
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter
from nonebot.adapters.onebot.v12 import Adapter as OnebotV12Adapter


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {"driver": "~fastapi+~websockets"}


@pytest.fixture(scope="session", autouse=True)
def load_adapters(nonebug_init: None):
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)
    driver.register_adapter(OnebotV12Adapter)
    driver.register_adapter(QQGuildAdapter)
    driver.register_adapter(TelegramAdapter)
    driver.register_adapter(ConsoleAdapter)


@pytest.fixture(scope="session", autouse=True)
def load_plugins(nonebug_init: None):
    nonebot.load_plugins("nonebot_plugin_all4one")
