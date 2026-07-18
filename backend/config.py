import os

# Kredensial Userbot
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Input dari Web App API
CHAT_ID = int(os.environ.get("CHAT_ID", 0))
OTA_URL = os.environ.get("OTA_URL", "")
PARTITIONS = os.environ.get("PARTITIONS", "")
