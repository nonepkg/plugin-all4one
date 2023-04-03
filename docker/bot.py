import nonebot
from nonebot.adapters.qqguild import Adapter as QQGUILDAdapter
from nonebot.adapters.telegram import Adapter as TELEGRAMAdapter
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.adapters.onebot.v12 import Adapter as ONEBOT_V12Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(QQGUILDAdapter)
driver.register_adapter(TELEGRAMAdapter)
driver.register_adapter(ONEBOT_V11Adapter)
driver.register_adapter(ONEBOT_V12Adapter)

nonebot.load_plugin("nonebot_plugin_all4one")

if __name__ == "__main__":
    nonebot.run()
