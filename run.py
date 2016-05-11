# -*- coding: utf-8 -*-
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
import tornado.web
import logging
import ssl
import os.path
import json
from controllers import RouteConfig

logging.basicConfig(level=logging.DEBUG)


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        pass

    def post(self):
        update_packet = json.loads(self.request.body)
        RouteConfig.process_update(update_packet)


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
    ])

if __name__ == "__main__":

    data_dir = "cert"

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(os.path.join(data_dir, "alfa.pem"),
                            os.path.join(data_dir, "alfa.key"))

    app = make_app()
    server = HTTPServer(app, ssl_options=ssl_ctx)
    server.listen(443)
    IOLoop.current().start()
