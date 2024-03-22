import nonebot
from nonebot.adapters.telegram import Adapter as TELEGRAMAdapter
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(TELEGRAMAdapter)
driver.register_adapter(ONEBOT_V11Adapter)

nonebot.load_plugin("nonebot_plugin_sentry")
nonebot.load_plugin("nonebot_plugin_all4one")

if __name__ == "__main__":
    nonebot.run()
