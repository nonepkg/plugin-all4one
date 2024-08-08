from pathlib import Path

import pytest
import nonebot
from sqlalchemy import delete
from pytest_mock import MockerFixture
from nonebug import NONEBOT_INIT_KWARGS, App
from nonebot.adapters.telegram import Adapter as TelegramAdapter
from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter
from nonebot.adapters.onebot.v12 import Adapter as OnebotV12Adapter


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx+~websockets",
        "sqlalchemy_database_url": "sqlite+aiosqlite:///:memory:",
        "alembic_startup_check": False,
    }


@pytest.fixture(scope="session", autouse=True)
def _load_adapters(nonebug_init: None):
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)
    driver.register_adapter(OnebotV12Adapter)
    driver.register_adapter(TelegramAdapter)


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
async def app(
    nonebug_init: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    nonebot.require("nonebot_plugin_all4one")
    from nonebot_plugin_orm import init_orm, get_session

    import nonebot_plugin_all4one.database

    mocker.patch("nonebot_plugin_orm._data_dir", tmp_path / "orm")

    await init_orm()

    with monkeypatch.context() as m:
        m.setattr(nonebot_plugin_all4one.database, "FILE_PATH", tmp_path)

        yield App()

    # 清空数据库
    from nonebot_plugin_all4one.database import File

    async with get_session() as session:
        await session.execute(delete(File))


@pytest.fixture
async def session(app: App):
    from nonebot_plugin_orm import get_session

    async with get_session() as session:
        yield session
