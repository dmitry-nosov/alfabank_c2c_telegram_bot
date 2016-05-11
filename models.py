# -*- coding: utf-8 -*-
import logging
import requests
import json
import shutil
logging.basicConfig(level=logging.DEBUG)
from bson.objectid import ObjectId
from custom_exceptions import ChatMessageNotPrivate
from app_settings import AppSettings
from pydub import AudioSegment
import xml.etree.ElementTree as ET
from datetime import datetime
from api.docdb_api import DocdbApi


class ChatMessage(object):

    UPDATE_TYPE_MESSAGE = "message"
    UPDATE_TYPE_CALLBACK = "callback_query"

    MESSAGE_PRIVATE = "private"

    def get_bot_commands(self, message):
        bot_commands = []
        try:
            for entity in message['entities']:
                if entity['type'] == 'bot_command':
                    command_code = message['text'][entity['offset'] + 1:entity['offset'] + entity['length']]
                    if entity['offset'] == 0:
                        self.is_command = True
                        self.command_code = command_code
                    bot_commands.append(command_code)
        except KeyError:
            pass
        return bot_commands

    def __init__(self, message, type=UPDATE_TYPE_MESSAGE):
        self.is_command = False
        self.command_code = ""
        self.data = ""
        self.voice = ""
        self.has_voice = False
        self.voice_file_id = ""
        self.phone = ""
        self.message_type = type
        if type == ChatMessage.UPDATE_TYPE_CALLBACK:
            self.data = message['data']
            message = message['message'] #reuse message from a callback parent

        self.message_date = message['date'] #timestamp
        self.chat_id = message['chat']['id'] #integer

        if (message['chat']['type'] != ChatMessage.MESSAGE_PRIVATE):
            raise ChatMessageNotPrivate("The message type should be 'group' whereas it is %s" % message['chat']['type'])

        self.message_id = message['message_id'] #use in replies

        if type == ChatMessage.UPDATE_TYPE_MESSAGE:        
            self.bot_commands = self.get_bot_commands(message)
            try:
                self.phone = message['contact']['phone_number']
            except KeyError:
                pass
        try:
            if message['voice']:
                self.has_voice = True
                self.voice_file_id = message['voice']['file_id']
        except KeyError:
            pass                

    @staticmethod
    def process_audio_input(file_id):
        file_path = requests.get(AppSettings.TELEGRAM_API_URL+AppSettings.BOT_TOKEN+"/getFile", params={"file_id": file_id}).json()['result']['file_path']
        r = requests.get(AppSettings.TELEGRAM_API_URL + AppSettings.TELEGRAM_FILE_API_URL + AppSettings.BOT_TOKEN + '/' + file_path, stream=True)
        temp_file = "voice_files/%s.ogg" % file_id 
        if r.status_code == 200:
            with open(temp_file, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
        else:
            return ''
        ogg_file = AudioSegment.from_ogg(temp_file)
        mp3_file = "voice_files/%s.mp3" % file_id
        ogg_file.export(mp3_file, format="mp3")

        files = {"file": open(mp3_file, "rb")}
        headers = {"content-type": "audio/x-mpeg-3"}

        r = requests.post(AppSettings.YANDEX_SPEECH_API % AppSettings.YANDEX_SPEECH_KEY,
                          files=files, headers=headers)
        logging.info("RECEIVED FROM YANDEX:" + r.text)

        result_text = r.text.encode('ascii',errors='ignore')
               
        root = ET.fromstring(result_text)
        variant = root.find('variant')
        if variant is not None:
            if variant.text:                
                return filter(lambda i: i.isdigit(), variant.text)
        return ''


class UserState(object):

    STATE_ERROR = "error"

    STATE_UNAUTH = "unauth"
    STATE_UNAUTH_C_GET_PHONE = "start"
    STATE_UNAUTH_C_VERIFY_PHONE = "phone_verify"

    STATE_NOCARD = "nocard"
    STATE_NOCARD_C_INIT = "start"
    STATE_NOCARD_C_ADD = "1"

    STATE_AUTH = "authorized"
    STATE_AUTH_C_INIT = "start"
    STATE_AUTH_C_TRANSFER_SELECT_CARD = "1"
    STATE_AUTH_C_TRANSFER_TRANSFER = "transfer"

    @staticmethod
    def get_state(chat_id):
        user_state = DocdbApi.find_one(DocdbApi.USER_STATE, {"id": str(chat_id)})

        if not user_state:
            user_state = {"id": str(chat_id), "state": UserState.STATE_UNAUTH, "command_code": UserState.STATE_UNAUTH_C_GET_PHONE}
            DocdbApi.update_one(DocdbApi.USER_STATE, user_state)
        return user_state

    @staticmethod
    def set_command_value(chat_id, user_state, command_code, value):
        command_value = DocdbApi.find_one(DocdbApi.COMMAND_VALUE, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code})
        if command_value:
            DocdbApi.update_one(DocdbApi.COMMAND_VALUE, {"id": command_value['id'], "chat_id": chat_id, "user_state": user_state, "command_code": command_code, "value": value})        
        else:
            DocdbApi.update_one(DocdbApi.COMMAND_VALUE, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code, "value": value})


    @staticmethod
    def get_command_value(chat_id, user_state, command_code):
        command_value = DocdbApi.find_one(DocdbApi.COMMAND_VALUE, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code})       
        if command_value:
            return command_value['value']
        else:
            return ""

    @staticmethod
    def set_command_context(chat_id, user_state, command_code, value):
        command_context = DocdbApi.find_one(DocdbApi.COMMAND_CONTEXT, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code})
        if command_context:
            DocdbApi.update_one(DocdbApi.COMMAND_CONTEXT, {"id": command_context['id'], "chat_id": chat_id, "user_state": user_state, "command_code": command_code, "context": value})
        else:
            DocdbApi.update_one(DocdbApi.COMMAND_CONTEXT, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code, "context": value})

    @staticmethod
    def get_command_context(chat_id, user_state, command_code):
        command_value = DocdbApi.find_one(DocdbApi.COMMAND_CONTEXT, {"chat_id": chat_id, "user_state": user_state, "command_code": command_code})        
        if command_value:
            return command_value['context']
        else:
            return ""

    @staticmethod
    def set_state(chat_id, state, command_code):
        DocdbApi.update_one(DocdbApi.USER_STATE, {"id": str(chat_id), "state": state, "command_code": command_code})        
         

class ViewParams:
    VIEW_CUSTOM_KEYBOARD = 1
    VIEW_SIMPLE = 2
    VIEW_DIGITAL_KEYBOARD = 3
    VIEW_DYNAMIC_ITEMS_KEYBOARD = 4

    #Custom keys on digital inline keyboards
    KEYBOARD_KEY_OK = 11
    KEYBOARD_KEY_DELETE = 10


class UserCard(object):

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.number = kwargs['number'][-4:]
        self.exp_date = datetime.strptime(
            kwargs['exp_date'], '%Y-%m-%d').strftime('%Y%m')

    def __str__(self):
        return "UserCard (id: {id}, number: {number})".format(
            id=self.id, number=self.number)

    def pack(self):
        return "%s~%s~%s" % (self.id, self.number, datetime.strptime(
            self.exp_date, '%Y%m').strftime('%Y-%m-01'))

    @staticmethod
    def unpack(obj_str):
        id, number, exp_date = obj_str.split('~')
        return UserCard(id = id, number = number, exp_date = exp_date)


class User(object):

    def __init__(self, chat_id):
        self.user_id = ''
        self.access_token = ''

        user_obj = DocdbApi.find_one(DocdbApi.USER, {"id": str(chat_id)})

        try:
            self.user_id = user_obj['user_id']
            self.access_token = user_obj['access_token']
        except (KeyError, TypeError):
            pass

    @staticmethod
    def add(chat_id, parameter, value):
        user_obj = DocdbApi.find_one(DocdbApi.USER, {"id": str(chat_id)})
        if user_obj:
            user_obj.update({parameter:value})
            DocdbApi.update_one(DocdbApi.USER, user_obj)
        else:
            user_obj = {"id": str(chat_id)}
            user_obj.update({parameter:value})
            DocdbApi.update_one(DocdbApi.USER, user_obj)

            


