import pydocumentdb.document_client as document_client
from app_settings import AppSettings
import time
import logging

class DocdbApi(object):

    USER = None
    COMMAND_VALUE = None
    USER_STATE = None
    COMMAND_CONTEXT = None

    client = document_client.DocumentClient(AppSettings.DOCUMENTDB_HOST, {'masterKey': AppSettings.DOCUMENTDB_KEY})
    db = next((data for data in client.ReadDatabases() if data['id'] == AppSettings.DOCUMENTDB_DATABASE))

    for data in client.ReadCollections(db['_self']):
        if data['id'] == 'user':
            USER = data['_self']
        elif data['id'] == 'command_value':
            COMMAND_VALUE = data['_self']
        elif data['id'] == 'user_state':
            USER_STATE = data['_self']
        elif data['id'] == 'command_context':
            COMMAND_CONTEXT = data['_self']

    @staticmethod
    def find_one(collection, parameters):
        query = ""
        request_parameters = []
        for i, key in enumerate(parameters.keys()):
            query += "c.{key}=@{key}".format(key = key)
            request_parameters.append({"name": "@{key}".format(key = key), "value": parameters[key]})
            if i + 1 < len(parameters.keys()):        
                query += " AND "
        current_time = time.time()
        try:
            query_result = next(DocdbApi.client.QueryDocuments(collection, {
                    "query": "SELECT TOP 1 * FROM c WHERE %s" % query,
                    "parameters": request_parameters
                }).__iter__())
        except StopIteration:
            query_result = None
        logging.info("[DB REQUEST TIME (GET)] %s" % (time.time() - current_time))
        return query_result

    @staticmethod    
    def update_one(collection, doc):
        current_time = time.time()
        res = DocdbApi.client.UpsertDocument(collection, doc)
        logging.info("[DB REQUEST TIME (SET)] %s" % (time.time() - current_time))
        return res







