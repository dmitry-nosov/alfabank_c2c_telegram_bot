# -*- coding: utf-8 -*-
from app_settings import AppSettings
import base64
import json
from datetime import datetime
import requests
import logging
import time

class AlfaApiError(Exception):
    pass

class AlfaApi(object):

    STATUS_COMPLETED = 'COMPLETED'

    def _restart_if_fails(f):
        def g(*args, **kwargs):
            for attempt in range(AppSettings.NUMBER_OF_ATTEMPTS):
                try:
                    return f(*args, **kwargs)                    
                except AlfaApiError:
                    continue
            raise AlfaApiError
        return g

    def _authorized(f):
        def g(*args, **kwargs):
            user = kwargs['user']
            headers = {"Authorization": "Bearer %s" % user.access_token}
            kwargs['headers'] = headers
            return f(*args, **kwargs)
        return g

    @staticmethod
    def request(method, url, **kwargs):
        current_time = time.time()
        try:
            r = requests.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            raise AlfaApiError
        logging.info("[ALFA REQUEST TIME] %s" % (time.time() - current_time))

        if r.status_code != requests.codes.ok:
            raise AlfaApiError
        logging.info(r.text)
        return r

    @staticmethod
    @_restart_if_fails
    def send_phone_number(chat_id, phone_number):
        headers = {
            "Authorization": "Basic %s" %
            base64.b64encode(
                AppSettings.ALFA_PARTNER_CREDS),
            "Cache-Control": "no-cache"}
        r = AlfaApi.request(
            'post',
            AppSettings.ALFA_URL +
            "/uapidemo/api/oauth/users/authorize?sender=%s&alerttype=sms" %
            phone_number,
            headers=headers)
        return json.loads(r.text)
        

    @staticmethod
    def send_sms_code(chat_id, phone_number, sms_code):
        headers = {
            "Authorization": "Basic %s" %
            base64.b64encode(
                AppSettings.ALFA_PARTNER_CREDS),
            "Cache-Control": "no-cache"}
        r = AlfaApi.request(
            'post',
            AppSettings.ALFA_URL +
            "/uapidemo/api/oauth/token?username=%s&password=%s&scope=read&grant_type=one_time_password" %
            (phone_number,
             sms_code),
            headers=headers)
        return json.loads(r.text)


    @staticmethod
    @_authorized
    def add_card(card_number, exp_date, **kwargs):
        r = AlfaApi.request('post', AppSettings.ALFA_URL + "/uapidemo/api/v1/users/%s/cards" % kwargs['user'].user_id, headers=kwargs['headers'], json={
            "number": card_number,
            "exp_date": exp_date
        })

    @staticmethod
    @_authorized
    def get_cards(**kwargs):
        user_cards = []
        r = AlfaApi.request(
            'get',
            AppSettings.ALFA_URL +
            "/uapidemo/api/v1/users/%s/cards" %
            kwargs['user'].user_id,
            headers=kwargs['headers'])
        return json.loads(r.text)

    @staticmethod
    @_authorized
    def transfer_c2c_init(from_cvv, card, to_card_number, amount, **kwargs):
        r = AlfaApi.request('put', AppSettings.ALFA_URL + "/uapidemo/api/v1/transfers", headers=kwargs['headers'],
                            json={
            "sender": {
                "card": {
                    "id": card.id,
                    "exp_date": card.exp_date,
                    "cvv": from_cvv
                }
            },
            "recipient": {
                "card": {
                    "number": to_card_number
                }
            },
            "amount": amount,
            "currency": "RUR",
            "client_ip": "127.0.0.1"
        })

        return json.loads(r.text)['md']

    @staticmethod
    @_authorized
    def transfer_c2c_complete(md, **kwargs):
        r = AlfaApi.request('post', AppSettings.ALFA_URL + "/uapidemo/api/v1/transfers", headers=kwargs['headers'],
                            json={"md": md,
                                  "pares": "eJzVWFmzm0zO/iupzKUrYbOx/ZZzphqa1Q..."
                                  })

        if json.loads(r.text)['status'] != AlfaApi.STATUS_COMPLETED:
            raise AlfaApiError