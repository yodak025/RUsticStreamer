#!/usr/bin/python3

import argparse
import asyncio
import json
import os
import random

from aiohttp import web
from aiortc import RTCSessionDescription
from RusticSipClasses import SLEEP_TIME, RusticUdpProtocol, RusticSipProtocol

ROOT = os.path.dirname(__file__)

NAME = "Front"

IP_WEB = "127.0.0.1"
PORT_WEB = 8080
ADDR_STR_WEB = f"{IP_WEB}:{PORT_WEB}"

IP_SIP = "127.0.0.1"
PORT_SIP = random.randint(1024, 49151)
ADDR_STR_SIP = f"{IP_SIP}:{PORT_SIP}"

SIG_IP = "127.0.0.1"
SIG_PORT = 5060
SIG_ADDR_STR = f"{SIG_IP}:{SIG_PORT}"



SERVE_TIME = 3600


class FrontUDP(RusticUdpProtocol):
    async def init_consume_signalling(self, call_id, body):
        await self.sip_sessions[call_id].consume_signalling(body)


class FrontSIP(RusticSipProtocol):
    def __init__(self, _address, _name, _call_id=None):
        super().__init__(_address, _name, _call_id)
        self.transport = None
        self.option_message = None
        self.selected_streamer = None
        self.sdp_answer = None

    async def get_options(self):
        while True:
            if self.option_message is not None:
                options = self.option_message
                return options

            await asyncio.sleep(SLEEP_TIME)

    async def answer_is_received(self):
        while True:
            if self.sdp_answer is not None:
                return self.sdp_answer
            await asyncio.sleep(SLEEP_TIME)

    async def greeting(self, transport, addr=None):
        self.transport = transport
        self.options(SIG_ADDR_STR)
        await self.send_secure_sip_message(self.generate_message("send"), self.transport, [SIG_IP, SIG_PORT])

    async def consume_signalling(self, body):
        self.via_address = "127.0.0.1:5060"
        self.invite(self.selected_streamer, body)
        await self.send_secure_sip_message(self.generate_message("send"), self.transport, [SIG_IP, SIG_PORT])

    async def response(self, data, address, transport):
        if data.type == "200 OK":
            self._received = True
            self.option_message = data.body

        if data.type == "100 Trying":
            self._received = True

        elif data.type == "202 Accepted":
            self.sdp_answer = data.body
            self.via_address = "****"
            self.ack(SIG_ADDR_STR)
            await self.send_sip_message(self.generate_message("send"), self.transport, [SIG_IP, SIG_PORT])

        else:
            pass


class WebConnection:
    def __init__(self):
        self.connections = {}

        self.udp_connection = None

    @staticmethod
    def get_client_info(msg):
        try:
            client_id = msg["client_id"]
            content = msg["content"]
        except KeyError:
            raise Exception("corrupted json, should be {client_id:'id', content:{}")
        return client_id, content

    async def create_datagram_endpoint(self):
        loop = asyncio.get_running_loop()
        self.udp_connection = FrontUDP([IP_SIP, PORT_SIP], FrontSIP)

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: self.udp_connection,
            local_addr=(IP_SIP, PORT_SIP))

        try:
            await asyncio.sleep(SERVE_TIME)  # Serve for 1 hour. Should be for 24h.
        except KeyboardInterrupt:
            pass  # Mejor que haga algo.
        finally:
            # loop.run_until_complete(pc.close())
            transport.close()

    async def index(self, request):
        if self.udp_connection is None:
            asyncio.ensure_future(
                self.create_datagram_endpoint()
            )
        content = open(os.path.join(ROOT, "html/index.html"), "r").read()
        return web.Response(content_type="text/html", text=content)

    @staticmethod
    async def css(request):
        content = open(os.path.join(ROOT, "CSS/styles.css"), "r").read()
        return web.Response(content_type="text/css", text=content)

    @staticmethod
    async def show_options(request):
        content = open(os.path.join(ROOT, "JavaScript/client.js"), "r").read()
        return web.Response(content_type="application/javascript", text=content)

    async def register(self, request):
        msg = await request.json()
        client_id, content = self.get_client_info(msg)
        if client_id in self.connections:
            response = "denied"
        else:
            response = "accepted"

        return web.Response(
            content_type="application/json",
            text=json.dumps({"request": response}),
        )

    async def options(self, request):
        msg = await request.json()
        client_id, content = self.get_client_info(msg)

        call_id = self.udp_connection.create_sip_session(client_id)
        self.connections[client_id] = call_id

        await self.udp_connection.ensure_greeting(self.connections[client_id])
        options = await self.udp_connection.sip_sessions[self.connections[client_id]].get_options()

        return web.Response(
            content_type="application/json",
            text=options,
        )

    async def streamer_address(self, request):

        msg = await request.json()
        client_id, content = self.get_client_info(msg)

        call_id = self.connections[client_id]
        self.udp_connection.sip_sessions[call_id].selected_streamer = content["address"]

    async def offer(self, request):
        msg = await request.json()
        client_id, offer_ = self.get_client_info(msg)
        call_id = self.connections[client_id]

        await self.udp_connection.init_consume_signalling(call_id, json.dumps(offer_))
        answer_ = await self.udp_connection.sip_sessions[call_id].answer_is_received()

        while True:
            obj = RTCSessionDescription(**json.loads(answer_))
            if isinstance(obj, RTCSessionDescription):
                return web.Response(
                    content_type="application/json",
                    text=json.dumps(
                        {"sdp": obj.sdp, "type": obj.type}
                    ),
                )


def parse_args():
    global PORT_WEB, ADDR_STR_WEB, SIG_IP, SIG_PORT, SIG_ADDR_STR

    parser = argparse.ArgumentParser(description="Front")
    parser.add_argument("tcp_port", type=int, default=PORT_WEB, help="Port to listen")
    parser.add_argument("ip", type=str, default=IP_WEB, help="Signalling IP address")
    parser.add_argument("udp_port", type=int, default=PORT_WEB, help="Signalling port")

    arguments = parser.parse_args()

    PORT_WEB = arguments.tcp_port
    ADDR_STR_WEB = f"{IP_WEB}:{PORT_WEB}"

    SIG_IP = arguments.ip
    SIG_PORT = arguments.udp_port
    SIG_ADDR_STR = f"{SIG_IP}:{SIG_PORT}"


def main():
    pcs = set()
    parse_args()

    async def on_shutdown(app):
        # close peer connections
        coros = [pc.close() for pc in pcs]
        await asyncio.gather(*coros)
        pcs.clear()

    filename = ROOT + '/options/options.xml'
    if os.path.exists(filename):
        os.remove(filename)

    resources = WebConnection()

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", resources.index)
    app.router.add_get("/client.js", resources.show_options)
    app.router.add_get("/styles.css", resources.css)
    app.router.add_post("/register", resources.register)
    app.router.add_post("/options", resources.options)
    app.router.add_post("/streamer", resources.streamer_address)
    app.router.add_post("/offer", resources.offer)
    web.run_app(app, host=IP_WEB, port=PORT_WEB)


if __name__ == "__main__":
    main()
