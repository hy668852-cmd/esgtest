import os

OTA_URL = "https://api.tenclass.net/xiaozhi/ota"
DEFAULT_MAC_ADDR = "00:00:00:00:00:AA"
# 从环境变量读取端口，如果没有设置则使用默认值51000
PORT = int(os.getenv("PORT", "51000"))
