# -*- coding: utf-8 -*-
from models import ChatMessage, UserState, ViewParams, UserCard, User
from views import AbstractView, GetPhoneView, UnauthErrorView, VerifyPhoneView, NoCardInitView, NoCardAddCardView, AuthInitView, AuthSelectCardView, AuthTransferView
from api.alfa_api import AlfaApi, AlfaApiError
from custom_exceptions import ChatMessageNotPrivate
from resources import ErrorText, MessageText
import logging
import requests
import json
import string
from app_settings import AppSettings

logging.basicConfig(level=logging.DEBUG)

class AbstractController(object):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):
        UserState.set_command_value(chat_message.chat_id, user_state, command_code, "") #empty phone number/confirmation number
        UserState.set_state(chat_message.chat_id, user_state, command_code)

        user_view = router.get_route(user_state, command_code)['view']
        view_params = user_view.get()
        view_params.update({'chat_id': chat_message.chat_id})
        user_view.render(**view_params)

    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):
        pass

class UnauthErrorController(AbstractController):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):
        pass #a user must not call it

class GetPhoneController(AbstractController):

    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):

        if chat_message.phone:
            render_context = AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING)
            view_render_extras = {'message_id': render_context['result']['message_id'], 'is_update': True}

            try:                
                user_obj = AlfaApi.send_phone_number(chat_message.phone)  
                User.add(chat_message.chat_id, "user_id", user_obj['user_id'])

                UserState.set_command_value(chat_message.chat_id, user_state, command_code, chat_message.phone) #fill phone number
                command_code = UserState.STATE_UNAUTH_C_VERIFY_PHONE            
                UserState.set_state(chat_message.chat_id, user_state, command_code)                
                AbstractView.show_toast(chat_message.chat_id, MessageText.MESSAGE_CORRECT_PHONE, view_render_extras)
                return {"run_next": True}

            except AlfaApiError:
                command_code = UserState.STATE_ERROR
                user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)
                view_params.update(view_render_extras)
                user_view.render(**view_params)
        else:            
            AbstractView.show_toast(chat_message.chat_id, ErrorText.ERROR_NO_PHONE)           


class VerifyPhoneController(AbstractController):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):
        UserState.set_command_value(chat_message.chat_id, user_state, command_code, "") 
        UserState.set_state(chat_message.chat_id, user_state, command_code)

        phone_number = UserState.get_command_value(chat_message.chat_id, user_state, UserState.STATE_UNAUTH_C_GET_PHONE)
        phone_number = phone_number[0] + "-" + phone_number[1:4] + "-" + phone_number[4:7] + "-" + phone_number[7:]
        sms_code = ""
        sms_code = " ".join("{:-<6s}".format(sms_code))
        error = ""

        user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)

        view_params['text'] = view_params['text'].format(phone_number=phone_number, sms_code=sms_code, error=error)             
        user_view.render(**view_params)

    @staticmethod
    def update_sms_code_by_callback(chat_message, view_params, sms_code):
        view_render_extras = {"message_id": chat_message.message_id, "is_update": True}
        view_params.update(view_render_extras)
            
        key_code = int(chat_message.data)

        if (key_code < 10):
            if len(sms_code) < 6:
                sms_code += chat_message.data
            
        else:
            if key_code == ViewParams.KEYBOARD_KEY_DELETE:
                if len(sms_code) > 0:
                    logging.info("SMS_CODE before: %s" % sms_code)
                    sms_code = sms_code[:-1]
        return sms_code, view_render_extras

    @staticmethod
    def update_sms_code_by_audio(chat_message, view_params, sms_code):
        render_context = AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING)           
        sms_code = chat_message.process_audio_input(chat_message.voice_file_id)[:6]
        view_render_extras = {'message_id': render_context['result']['message_id'], 'is_update': True}
        view_params.update(view_render_extras)
        return sms_code, view_render_extras

    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):
        view_render_extras = {} #need to add this data to update a view instead of redrawing

        user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)

        temp_view_params_text = view_params['text']
        key_code = 0
        sms_code = UserState.get_command_value(chat_message.chat_id, user_state, command_code)
        error = ""
        phone_number = UserState.get_command_value(chat_message.chat_id, user_state, UserState.STATE_UNAUTH_C_GET_PHONE)
        phone_number_formatted = phone_number[0] + '-' + phone_number[1:4] + '-' + phone_number[4:7] + '-' + phone_number[7:]

        if (chat_message.message_type == ChatMessage.UPDATE_TYPE_CALLBACK):
            key_code = int(chat_message.data)
            sms_code, view_render_extras = VerifyPhoneController.update_sms_code_by_callback(chat_message, view_params, sms_code)

        #processing voice message
        elif chat_message.has_voice:
            sms_code, view_render_extras = VerifyPhoneController.update_sms_code_by_audio(chat_message, view_params, sms_code)

        UserState.set_command_value(chat_message.chat_id, user_state, command_code, sms_code)
        sms_code_formatted = ' '.join('{:-<6s}'.format(sms_code))               
        view_params['text'] = view_params['text'].format(phone_number=phone_number_formatted, sms_code=sms_code_formatted, error=error)
        return_value = None        

        #Handling result
        if ((chat_message.message_type == ChatMessage.UPDATE_TYPE_CALLBACK) and (key_code == ViewParams.KEYBOARD_KEY_OK)
            or (chat_message.voice)):
            try:
                AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING, view_render_extras)
                user_obj = AlfaApi.send_sms_code(phone_number, sms_code)  
                
                User.add(chat_id, "access_token", user_obj['access_token'])
                User.add(chat_id, "refresh_token", user_obj['refresh_token'])

                UserState.set_state(chat_message.chat_id, UserState.STATE_NOCARD, UserState.STATE_NOCARD_C_INIT)
                view_params['text'] = MessageText.MESSAGE_CORRECT_CODE
                view_params.update({'force_remove_inline': True})
                return_value = {'run_next': True}

            except AlfaApiError:
                error = ErrorText.ERROR_WRONG_SMS_CODE
                sms_code = ""
                UserState.set_command_value(chat_message.chat_id, user_state, command_code, sms_code)                
                sms_code_formatted = ' '.join('{:-<6s}'.format(sms_code)) 
                view_params['text'] = temp_view_params_text.format(phone_number=phone_number_formatted, sms_code=sms_code_formatted, error=error)

        user_view.render(**view_params)
        return return_value


class NoCardInitController(AbstractController):
    pass

class NoCardAddCardController(AbstractController):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):

        card_number = ""
        card_month = ""
        card_year = ""
        card_cvv = ""
        error = ""

        command_value = {"card_number": card_number, "card_month": card_month, "card_year": card_year, "card_cvv": card_cvv}

        UserState.set_command_value(chat_message.chat_id, user_state, command_code, json.dumps(command_value)) #empty card settings
        UserState.set_state(chat_message.chat_id, user_state, command_code)

        user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)
        
        card_number = " ".join("{:-<16s}".format(card_number))
        card_number = string.join([card_number[i: i+7]+"  " for i in range(0, 32, 8)])
        
        view_params['text'] = view_params['text'].format(card_number = card_number,
                                                         card_year = " ".join("{:-<2s}".format(card_year)),
                                                         card_month = " ".join("{:-<2s}".format(card_month)),
                                                         card_cvv = " ".join("{:-<3s}".format(card_cvv)),
                                                         error = error
                                                         )


        user_view.render(**view_params)

    @staticmethod
    def update_form_by_callback(chat_message, command_value):
        key_code = int(chat_message.data)
        error = ''
        card_add_success = False

        if (key_code < 10):
            if len(command_value['card_number']) < 16:
                command_value['card_number'] += chat_message.data
                    
            elif len(command_value['card_month']) < 2:
                command_value['card_month'] += chat_message.data

            elif len(command_value['card_year']) < 2:
                command_value['card_year'] += chat_message.data

            elif len(command_value['card_cvv']) < 3:
                command_value['card_cvv'] += chat_message.data                                

        else:
            if key_code == ViewParams.KEYBOARD_KEY_DELETE:

                if len(command_value['card_cvv']) > 0:
                    command_value['card_cvv'] = command_value['card_cvv'][:-1]

                elif len(command_value['card_year']) > 0:
                    command_value['card_year'] = command_value['card_year'][:-1]

                elif len(command_value['card_month']) > 0:
                    command_value['card_month'] = command_value['card_month'][:-1]
                    
                elif len(command_value['card_number']) > 0:
                    command_value['card_number'] = command_value['card_number'][:-1]

    @staticmethod
    def check_result(chat_message, view_render_extras, command_value):
        card_add_success = False
        error = ""
        try:
            AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING, view_render_extras)
            AlfaApi.add_card(command_value['card_number'], '20%s%s' % (command_value['card_year'], command_value['card_month']), user = User(chat_message.chat_id))
            card_add_success = True
        except AlfaApiError:
            error = ErrorText.ERROR_BANK_ERROR_INLINE
        return card_add_success, error

    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):
        view_render_extras = {} #need to add this data to update a view instead of redrawing
        card_add_success = False
        error = ""

        if (chat_message.message_type == ChatMessage.UPDATE_TYPE_CALLBACK):

            view_render_extras = {"message_id": chat_message.message_id, "is_update": True}
            command_value = json.loads(UserState.get_command_value(chat_message.chat_id, user_state, command_code))
            key_code = int(chat_message.data)

            NoCardAddCardController.update_form_by_callback(chat_message, command_value)
            UserState.set_command_value(chat_message.chat_id, user_state, command_code, json.dumps(command_value))

            if key_code == ViewParams.KEYBOARD_KEY_OK:
                card_add_success, error = NoCardAddCardController.check_result(chat_message, view_render_extras, command_value)

            user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)

            card_number = ' '.join('{:-<16s}'.format(command_value['card_number']))
            card_number = string.join([card_number[i: i+7]+'  ' for i in range(0, 32, 8)])
        
            view_params['text'] = view_params['text'].format(card_number = card_number,
                                                                card_year = ' '.join('{:-<2s}'.format(command_value['card_year'])),
                                                                card_month = ' '.join('{:-<2s}'.format(command_value['card_month'])),
                                                                card_cvv = ' '.join('{:-<3s}'.format(command_value['card_cvv'])),
                                                                error = error
                                                                )
            return_value = None

            if card_add_success:
                UserState.set_state(chat_message.chat_id, UserState.STATE_AUTH, UserState.STATE_AUTH_C_INIT)
                view_params['text'] = MessageText.MESSAGE_CORRECT_CARD_ADD
                view_params.update({'force_remove_inline': True})
                return_value = {'run_next': True}
            
            view_params.update(view_render_extras)
            user_view.render(**view_params)            
            return return_value
        else:           
            AbstractView.show_toast(chat_message.chat_id, ErrorText.ERROR_INPUT_UNSUPPORTED)


class AuthInitController(AbstractController):
    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):
        pass


class AuthSelectCardController(AbstractController):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):

        UserState.set_command_value(chat_message.chat_id, user_state, command_code, "")
        UserState.set_state(chat_message.chat_id, user_state, command_code)

        user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)
        
        render_context = AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING)
        view_render_extras = {'message_id': render_context['result']['message_id'], 'is_update': True}
        try:
            user_cards = []
            cards_json = AlfaApi.get_cards(user = User(chat_message.chat_id))
            for card_obj in cards_json:
                user_cards.append(UserCard(**card_obj))

            inline_buttons = []
            for card in user_cards:
                inline_buttons.append([{'text': MessageText.CARD_NAME % card.number, 'callback_data': card.pack()}])
                logging.info(card.pack())
            view_params.update({'inline_buttons': inline_buttons})            
            
            view_params.update(view_render_extras)
            user_view.render(**view_params)

        except AlfaApiError:
            AbstractView.show_toast(chat_message.chat_id, ErrorText.ERROR_BANK_ERROR_TOAST, view_render_extras)


    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):

        view_render_extras = {} #need to add this data to update a view instead of redrawing

        if (chat_message.message_type == ChatMessage.UPDATE_TYPE_CALLBACK):
            view_render_extras = {'message_id': chat_message.message_id, 'is_update': True}
            UserState.set_command_value(chat_message.chat_id, user_state, command_code, chat_message.data)

            render_context = AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING, view_render_extras)
            UserState.set_command_context(chat_message.chat_id, user_state, command_code, json.dumps(render_context))
            UserState.set_state(chat_message.chat_id, user_state, UserState.STATE_AUTH_C_TRANSFER_TRANSFER)
            return {'run_next': True}
        else:
            AbstractView.show_toast(chat_message.chat_id, ErrorText.ERROR_INPUT_UNSUPPORTED, view_render_extras)

class AuthTransferController(AbstractController):
    @staticmethod
    def run_command(user_state, command_code, chat_message, router):

        to_card_number = ""
        card_cvv = ""
        transfer_sum = ""
        error = ""
        command_value = {"to_card_number": to_card_number, "card_cvv": card_cvv, "transfer_sum":transfer_sum}

        UserState.set_state(chat_message.chat_id, user_state, command_code)
        UserState.set_command_value(chat_message.chat_id, user_state, command_code, json.dumps(command_value)) 

        render_context = json.loads(UserState.get_command_context(chat_message.chat_id, user_state, UserState.STATE_AUTH_C_TRANSFER_SELECT_CARD))        
        view_render_extras = {'message_id': render_context['result']['message_id'], 'is_update': True}

        user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)

        to_card_number = ' '.join('{:-<16s}'.format(to_card_number))
        to_card_number = string.join([to_card_number[i: i+7]+'  ' for i in range(0, 32, 8)])

        user_card = UserCard.unpack(UserState.get_command_value(chat_message.chat_id, user_state, UserState.STATE_AUTH_C_TRANSFER_SELECT_CARD))

        from_card_number = user_card.number
        
        view_params['text'] = view_params['text'].format(from_card_number = from_card_number, 
                                                         to_card_number = to_card_number,
                                                         card_cvv = ' '.join('{:-<3s}'.format(card_cvv)),
                                                         transfer_sum = ' '.join('{:-<5s}'.format(transfer_sum)),
                                                         error = error
                                                         )


        view_params.update(view_render_extras)
        user_view.render(**view_params)

    @staticmethod
    def update_form_by_callback(chat_message, command_value):
        key_code = int(chat_message.data)

        if (key_code < 10):
            if len(command_value['card_cvv']) < 3:
                command_value['card_cvv'] += chat_message.data
                    
            elif len(command_value['to_card_number']) < 16:
                command_value['to_card_number'] += chat_message.data

            elif len(command_value['transfer_sum']) < 5:
                command_value['transfer_sum'] += chat_message.data

        else:
            if key_code == ViewParams.KEYBOARD_KEY_DELETE:

                if len(command_value['transfer_sum']) > 0:
                    command_value['transfer_sum'] = command_value['transfer_sum'][:-1]

                elif len(command_value['to_card_number']) > 0:
                    command_value['to_card_number'] = command_value['to_card_number'][:-1]

                elif len(command_value['card_cvv']) > 0:
                    command_value['card_cvv'] = command_value['card_cvv'][:-1]



    @staticmethod            
    def check_result(chat_message, view_render_extras, command_value, user_card):
        error = ""
        card_add_success = False
        try:
            AbstractView.show_toast(chat_message.chat_id, MessageText.STATE_AUTH_LOADING, view_render_extras)

            md = AlfaApi.transfer_c2c_init(command_value['card_cvv'], 
                                            user_card,
                                            command_value['to_card_number'],
                                            command_value['transfer_sum'],
                                            user = User(chat_message.chat_id))

            AlfaApi.transfer_c2c_complete(md, user = User(chat_message.chat_id))
            card_add_success = True
        except AlfaApiError:
            error = ErrorText.ERROR_BANK_ERROR_INLINE
        return card_add_success, error
     

    @staticmethod
    def complete_command(user_state, command_code, chat_message, router):
        view_render_extras = {} #need to add this data to update a view instead of redrawing
        error = ""
        card_add_success = False #TODO: design the correct handling of the alfa API

        if (chat_message.message_type == ChatMessage.UPDATE_TYPE_CALLBACK):
            key_code = int(chat_message.data)

            user_card = UserCard.unpack(UserState.get_command_value(chat_message.chat_id, user_state, UserState.STATE_AUTH_C_TRANSFER_SELECT_CARD))
            from_card_number = user_card.number

            view_render_extras = {'message_id': chat_message.message_id, 'is_update': True}
            command_value = json.loads(UserState.get_command_value(chat_message.chat_id, user_state, command_code))

            AuthTransferController.update_form_by_callback(chat_message, command_value)            
            UserState.set_command_value(chat_message.chat_id, user_state, command_code, json.dumps(command_value))

            if key_code == ViewParams.KEYBOARD_KEY_OK:
                card_add_success, error = AuthTransferController.check_result(chat_message, view_render_extras, command_value, user_card)

            user_view, view_params = router.get_view(user_state, command_code, chat_message.chat_id)

            to_card_number = ' '.join('{:-<16s}'.format(command_value['to_card_number']))
            to_card_number = string.join([to_card_number[i: i+7]+'  ' for i in range(0, 32, 8)])
        
            view_params['text'] = view_params['text'].format(from_card_number=from_card_number, 
                                                             to_card_number = to_card_number,
                                                             card_cvv = ' '.join('{:-<3s}'.format(command_value['card_cvv'])),
                                                             transfer_sum = command_value['transfer_sum'],
                                                             error = error
                                                                )



            if card_add_success:
                UserState.set_state(chat_message.chat_id, UserState.STATE_AUTH, UserState.STATE_AUTH_C_INIT)
                view_params['text'] = MessageText.MESSAGE_CORRECT_TRANSFER
                view_params.update({'force_remove_inline': True})
            
            view_params.update(view_render_extras)
            user_view.render(**view_params)            
        else:
            AbstractView.show_toast(chat_message.chat_id, ErrorText.ERROR_INPUT_UNSUPPORTED, view_render_extras)

class RouteConfig(object):

    STATE_COMMANDS_MAP = {
        UserState.STATE_UNAUTH:[{"code": UserState.STATE_UNAUTH_C_GET_PHONE,
                       "controller": GetPhoneController,
                       "view": GetPhoneView
                       },
                      {"code": UserState.STATE_UNAUTH_C_VERIFY_PHONE,
                       "controller": VerifyPhoneController,
                       "view": VerifyPhoneView,
                       },
                      {"code": UserState.STATE_ERROR,
                       "controller": UnauthErrorController,
                       "view": UnauthErrorView,
                       }],
        UserState.STATE_NOCARD: [{"code": UserState.STATE_NOCARD_C_INIT,
                       "controller": NoCardInitController,
                       "view": NoCardInitView,
                       },
                       {"code": UserState.STATE_NOCARD_C_ADD,
                       "controller": NoCardAddCardController,
                       "view": NoCardAddCardView,
                       }],
        UserState.STATE_AUTH: [{"code": UserState.STATE_AUTH_C_INIT,
                       "controller": AuthInitController,
                       "view": AuthInitView,
                       },
                       {"code": UserState.STATE_AUTH_C_TRANSFER_SELECT_CARD,
                       "controller": AuthSelectCardController,
                       "view": AuthSelectCardView,
                       },
                       {"code": UserState.STATE_AUTH_C_TRANSFER_TRANSFER,
                       "controller": AuthTransferController,
                       "view": AuthTransferView,
                       }]
        }

    @staticmethod
    def command_fits_state(command_code, state):
        for command in RouteConfig.STATE_COMMANDS_MAP[state]:
            if command['code'] == command_code:
                return True
        return False

    @staticmethod
    def get_route(state, command_code):
        for command in RouteConfig.STATE_COMMANDS_MAP[state]:
            if command['code'] == command_code:
                return command

    @staticmethod
    def get_view(state, command_code, chat_id):
        user_view = RouteConfig.get_route(state, command_code)['view']
        view_params = user_view.get()
        view_params.update({"chat_id": chat_id})
        return (user_view, view_params)

    @staticmethod
    def process_update(update):
    
        try:
            chat_message = ChatMessage(update)
        except ChatMessageNotPrivate: #message must be private
            logging.info("Wrong group type")
            return

        user_state = UserState.get_state(chat_message.chat_id)

        if chat_message.is_command:
            method_name = "run_command"
            if RouteConfig.command_fits_state(chat_message.command_code, user_state['state']):
                command_name = chat_message.command_code
            else:
                return #just disregard the message
        else:
            method_name = "complete_command"
            command_name = user_state['command_code']

        method_results = getattr(RouteConfig.get_route(user_state['state'], command_name)['controller'], method_name)(user_state['state'], command_name, chat_message, RouteConfig)

        if method_results:
            try:
                if method_results['run_next']:
                    user_state = UserState.get_state(chat_message.chat_id)
                    getattr(RouteConfig.get_route(user_state['state'], user_state['command_code'])['controller'], "run_command")(user_state['state'], user_state['command_code'], chat_message, RouteConfig)
            except KeyError:
                pass
