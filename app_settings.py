# -*- coding: utf-8 -*-

class AppSettings(object):
    TELEGRAM_API_URL = "https://api.telegram.org/"
    BOT_TOKEN = "bot" + "USE_YOUR_API_KEY"
    TELEGRAM_FILE_API_URL = "file/"
    YANDEX_SPEECH_API = "https://asr.yandex.net/asr_xml?key=%s&uuid=12345678123456781234567812345678&topic=numbers&lang=ru-RU"
    YANDEX_SPEECH_KEY = "USE_YOUR_API_KEY"
    ALFA_PARTNER_CREDS = "TEST:test_user_secret"
    ALFA_URL = "https://testjmb.alfabank.ru"
    NUMBER_OF_ATTEMPTS = 5
    DOCUMENTDB_HOST = "https://alfabank.documents.azure.com:443/"
    DOCUMENTDB_KEY = "USE_YOUR_DB_KEY"
    DOCUMENTDB_DATABASE = "alfa_voice"
