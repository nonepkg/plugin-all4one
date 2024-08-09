import nonebot
from nonebot.adapters.discord import Adapter as DiscordAdapter
from nonebot.adapters.telegram import Adapter as TelegramAdapter
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(TelegramAdapter)
driver.register_adapter(OneBotV11Adapter)
driver.register_adapter(DiscordAdapter)

nonebot.load_plugin("nonebot_plugin_sentry")
nonebot.load_plugin("nonebot_plugin_all4one")

if __name__ == "__main__":
    # 不让 orm 弹该死的升级提示
    from nonebot_plugin_orm import _init_orm
    from nonebot_plugin_orm.migrate import AlembicConfig, upgrade

    _init_orm()
    upgrade(AlembicConfig())

    nonebot.run()
