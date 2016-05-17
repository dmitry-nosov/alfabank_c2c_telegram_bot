# -*- coding: utf-8 -*-

from models import ViewParams
from app_settings import AppSettings
import requests
from resources import ErrorText, MessageText
import logging
import json

class AbstractView(object):
    @staticmethod
    def get():
        pass

    @staticmethod
    def render(chat_id, view_type, text, is_update = False,  **kwargs):

        if view_type == ViewParams.VIEW_CUSTOM_KEYBOARD:
            params = {'chat_id': chat_id, 'text': text,'parse_mode': 'Markdown',  'reply_markup': {'keyboard': kwargs['controls'], 'resize_keyboard': True}}
        elif view_type == ViewParams.VIEW_SIMPLE:
            params = {'chat_id': chat_id, 'text': text,'parse_mode': 'Markdown'}
        elif view_type == ViewParams.VIEW_DIGITAL_KEYBOARD:
            params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown',
            'reply_markup': {'inline_keyboard': [[{'text': u'1', 'callback_data': '1'}, {'text': u'2', 'callback_data': '2'}, {'text': u'3', 'callback_data': '3'}],
                                                [{'text': u'4', 'callback_data': '4'}, {'text': u'5', 'callback_data': '5'}, {'text': u'6', 'callback_data': '6'}],
                                                [{'text': u'7', 'callback_data': '7'}, {'text': u'8', 'callback_data': '8'}, {'text': u'9', 'callback_data': '9'}],
                                                [{'text': u'<<', 'callback_data': '10'}, {'text': u'0', 'callback_data': '0'}, {'text': u'OK', 'callback_data': '11'}]
                                                ]}}
        elif view_type == ViewParams.VIEW_DYNAMIC_ITEMS_KEYBOARD:
            params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown',
            'reply_markup': {'inline_keyboard': kwargs['inline_buttons']}}

        try:
            if kwargs['force_remove_inline']:
                del params['reply_markup']
        except KeyError:
            pass

        if is_update:
            params.update({'message_id': kwargs['message_id']})
            render_response = requests.post(AppSettings.TELEGRAM_API_URL+AppSettings.BOT_TOKEN+"/editMessageText", json=params)            
        else:
            render_response = requests.post(AppSettings.TELEGRAM_API_URL+AppSettings.BOT_TOKEN+"/sendMessage", json=params)
        logging.info(render_response.text)

        try:
            return json.loads(render_response.text)
        except:
            return {}

    @staticmethod
    def show_toast(chat_id, text, view_render_extras={}):
        view_params = {'view_type': ViewParams.VIEW_SIMPLE, 'text': text}
        view_params.update({'chat_id': chat_id})
        view_params.update(view_render_extras)
        return AbstractView.render(**view_params)


class GetPhoneView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_CUSTOM_KEYBOARD, 'text': MessageText.STATE_UNAUTH_GET_PHONE_NUM, 'controls': [[{'text': MessageText.SEND_PHONE_NUMBER, 'request_contact': True}]]}


class UnauthErrorView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_SIMPLE, 'text': ErrorText.ERROR_NO_PHONE}

class VerifyPhoneView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_DIGITAL_KEYBOARD, 'text': MessageText.STATE_UNAUTH_VERIFY_PHONE}

class NoCardInitView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_CUSTOM_KEYBOARD, 'text': MessageText.STATE_NOCARD_INIT_CARD, 'controls': [[{'text': MessageText.ADD_CARD_FIRST}]]}

class NoCardAddCardView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_DIGITAL_KEYBOARD, 'text': MessageText.STATE_NOCARD_ADD_CARD}

class AuthInitView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_CUSTOM_KEYBOARD, 'text': MessageText.STATE_AUTH_INIT, 'controls': [[{'text': MessageText.TRANSFER_CARD_AUTH}, {'text': MessageText.ADD_CARD_AUTH}]]}

class AuthSelectCardView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_DYNAMIC_ITEMS_KEYBOARD, 'text': MessageText.STATE_AUTH_TRANSFER_SELECT_CARD}

class AuthTransferView(AbstractView):
    @staticmethod
    def get():
        return {'view_type': ViewParams.VIEW_DIGITAL_KEYBOARD, 'text': MessageText.STATE_AUTH_PERFORM_TRANSFER}