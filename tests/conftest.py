from pathlib import Path

import pytest
import nonebot
from sqlalchemy import delete
from nonebug import NONEBOT_INIT_KWARGS, App
from nonebot.adapters.console import Adapter as ConsoleAdapter
from nonebot.adapters.qqguild import Adapter as QQGuildAdapter
from nonebot.adapters.telegram import Adapter as TelegramAdapter
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter
from nonebot.adapters.onebot.v12 import Adapter as OnebotV12Adapter


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~websockets",
        "datastore_database_url": "sqlite+aiosqlite:///:memory:",
    }


@pytest.fixture(scope="session", autouse=True)
def load_adapters(nonebug_init: None):
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)
    driver.register_adapter(OnebotV12Adapter)
    driver.register_adapter(QQGuildAdapter)
    driver.register_adapter(TelegramAdapter)
    driver.register_adapter(ConsoleAdapter)

    nonebot.require("nonebot_plugin_all4one")
    from nonebot_plugin_all4one import obimpl

    obimpl.import_middlewares()


@pytest.fixture
def FakeMiddleware():
    from nonebot_plugin_all4one.middlewares import Middleware

    class FakeMiddleware(Middleware):
        @classmethod
        def get_name(cls):
            return "fake"

        def get_platform(self):
            return "fake"

        async def to_onebot_event(self, event):
            return []

    return FakeMiddleware


@pytest.fixture
async def app(nonebug_init: None, tmp_path: Path):
    nonebot.require("nonebot_plugin_all4one")
    from nonebot_plugin_datastore.db import init_db
    from nonebot_plugin_datastore import create_session
    from nonebot_plugin_datastore.config import plugin_config

    plugin_config.datastore_data_dir = tmp_path

    await init_db()

    yield App()

    # 清空数据库

    from nonebot_plugin_all4one.database import File

    async with create_session() as session:
        await session.execute(delete(File))
