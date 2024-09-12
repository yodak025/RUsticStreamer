#!/usr/bin/python3

import random
import uuid
import asyncio
import datetime
import sys

from asyncio import DatagramProtocol

SLEEP_TIME = 0.2


def _line_log(message):
    time = datetime.datetime.now()
    time_mark = time.strftime("%Y%m%d%H%M%S%f")[:-3]
    register_line = f"{time_mark} {message}"

    # Escribe la línea de registro en la salida de error (stderr)
    sys.stderr.write(register_line + '\n')


class RusticSipMessages:
    def __init__(self, data):
        self.type = None
        self.content_type = None
        self.body = None

        self.message = data.decode()
        lines = self.message.split("\r\n")

        if lines[0].split(" ")[0] == "SIP/2.0":
            self.type = lines[0].split(" ")[1] + " " + lines[0].split(" ")[2]
        elif lines[0].split(" ")[2] == "SIP/2.0":
            self.type = lines[0].split(" ")[0]
        else:
            print("Error: No se reconoce el tipo de mensaje")
            exit()

        self.sip_addr = {
            "via": lines[1].split(" ")[2],
            "from": lines[2].split(" ")[1].split("sip:")[1].split(">")[0],
            "to": lines[3].split(" ")[1].split("sip:")[1].split(">")[0]
        }

        if self.sip_addr["via"] != "****":
            self.via_addr = [
                lines[1].split(" ")[2].split(":")[0],
                lines[1].split(" ")[2].split(":")[1]
            ]
        else:
            pass

        self.from_addr = [
            lines[2].split(" ")[1].split(":")[1],
            lines[2].split(" ")[1].split(":")[2].split(">")[0]
        ]

        self.to_addr = [
            lines[3].split(" ")[1].split(":")[1],
            lines[3].split(" ")[1].split(":")[2].split(">")[0]
        ]

        self.call_id = lines[4].split(" ")[1]
        self.c_seq = lines[5].split(" ")[1]
        self.user_agent = lines[7].split(" ")[1]

        try:
            if lines[8].split(" ")[0] == "Content-Type:":
                self.body = lines[10]
                self.content_type = lines[8].split(" ")[1]

        except IndexError:
            pass


class RusticSipProtocol:
    def __init__(self, _address, _name, _call_id=None):

        from_address = _address[0] + ":" + str(_address[1])

        self.__TYPES__ = {
            "questions": ["OPTIONS", "REGISTER", "INVITE", "ACK", "BYE", "CANCEL"],
            "answers": ["100 Trying", "200 OK", "202 Accepted", "403 Forbidden"],
            "bodies": ["application/sdp", "application/json", "text/register"]
        }

        self._received = False

        self.type = None
        self.body_type = None
        self.sequence_number = random.randint(1, 10000)
        self.from_address = from_address
        self.to_address = None
        self.via_address = "****"
        self.user_agent = _name

        if _call_id is not None:
            self.call_id = _call_id
        else:
            self.call_id = str(uuid.uuid4())

        self.body = None

        self.last_msg = None

    @staticmethod
    def send_sip_message(msg, transport, direction):
        transport.sendto(msg.encode(), (direction[0], int(direction[1])))

    async def send_secure_sip_message(self, msg, transport, direction):
        while True:
            if self._received:
                self._received = False
                break
            transport.sendto(msg.encode(), (direction[0], int(direction[1])))
            await asyncio.sleep(SLEEP_TIME)

    def update_via(self, address):
        self.via_address = address

    def _add_body(self):
        if (self.body and self.body_type) is not None:

            if self.body_type == "application/sdp":
                return ("Content-Type: application/sdp\r\n"
                        "\r\n"
                        + self.body)
            elif self.body_type == "application/json":
                return ("Content-Type: application/json\r\n"
                        "\r\n"
                        + self.body)
            elif self.body_type == "text/register":
                return ("Content-Type: text/register\r\n"
                        "\r\n"
                        + self.body)
        else:
            return ""

    def _header_(self):
        message = (
            f"{self.type} {self.to_address} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP {self.via_address}\r\n"
            f"From: <sip:{self.from_address}>\r\n"
            f"To: <sip:{self.to_address}>\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self.sequence_number}\r\n"
            f"Contact: <sip:{self.from_address}>\r\n"
            f"User-Agent: {self.user_agent}\r\n"
        )
        self.sequence_number += 1
        return message
    
    def _answer_(self):
        message = (
            f"SIP/2.0 {self.type}\r\n"
            f"Via: SIP/2.0/UDP {self.via_address}\r\n"
            f"From: <sip:{self.from_address}>\r\n"
            f"To: <sip:{self.to_address}>\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self.sequence_number}\r\n"
            f"Contact: <sip:{self.from_address}>\r\n"
            f"User-Agent: {self.user_agent}\r\n"
        )
        self.sequence_number += 1
        return message

    def invite(self, destination, body):
        self.type = "INVITE"
        self.to_address = destination
        self.body_type = "application/sdp"
        self.body = body

    def options(self, destination):
        self.type = "OPTIONS"
        self.to_address = destination
        self.body_type = None
        self.body = None

    def register(self, destination, data):
        self.type = "REGISTER"
        self.to_address = destination
        self.body_type = "text/register"
        self.body = data

    def update(self, destination, data):
        self.type = "UPDATE"
        self.to_address = destination
        self.body_type = "text/register"
        self.body = data

    def ack(self, destination):
        self.type = "ACK"
        self.to_address = destination
        self.body_type = None
        self.body = None
        
    def bye(self, destination):
        self.type = "BYE"
        self.to_address = destination
        self.body_type = None
        self.body = None

    def cancel(self, destination):
        self.type = "CANCEL"
        self.to_address = destination
        self.body_type = None
        self.body = None

    def trying_100(self, destination):
        self.type = "100 Trying"
        self.to_address = destination
        self.body_type = None
        self.body = None

    def ok_200(self, destination, body=None):  # Override in Signalling
        self.type = "200 OK"
        self.to_address = destination
        self.body = body
        if body is not None:
            self.body_type = "application/json"
        else:
            self.body_type = None

    def accepted_202(self, destination, body):
        self.type = "202 Accepted"
        self.to_address = destination
        self.body_type = "application/sdp"
        self.body = body

    def forbidden_403(self, destination):
        self.type = "403 Forbidden"
        self.to_address = destination
        self.body_type = None
        self.body = None

    def generate_message(self, msg_type):
        if msg_type == "send":
            return self._header_() + self._add_body()
        elif msg_type == "answer":
            return self._answer_() + self._add_body()

    async def greeting(self, transport, addr):
        pass

    async def response(self, data, address, transport):
        pass


class RusticUdpProtocol(DatagramProtocol):

    def __init__(self, address, protocol):
        self.address: list = address
        self.message = None
        self.on_con_lost = None
        self.transport = None

        self.is_connection_made = False

        self.protocol = protocol
        self.sip_sessions: {RusticSipProtocol} = {}

    def connection_made(self, transport):
        self.transport = transport
        _line_log('Connectión Made')

        self.is_connection_made = True

    def datagram_received(self, data, addr):
        message = RusticSipMessages(data)

        _line_log(message.type + ' ' + ' Send to: < sip:' + message.to_addr[0] + ':' + message.to_addr[1] + '>' +
                  '  From: < sip:' + message.from_addr[0] + ':' + message.from_addr[1] + '>')

        try:
            sip_session = self.sip_sessions[message.call_id]
        except KeyError:
            # Si no hay entrada en .sip_sessions, se crea una nueva llamada con el call_id del mensaje
            new_call_id = self.create_sip_session(message.user_agent, message.call_id)
            sip_session = self.sip_sessions[new_call_id]

        asyncio.ensure_future(sip_session.response(message, addr, self.transport))

    def error_received(self, exc):
        print('Error received:', exc)

    def create_sip_session(self, name, call_id=None):
        new_call = self.protocol(
            self.address,
            name,
            call_id
        )

        key = new_call.call_id
        self.sip_sessions[key] = new_call
        return key

    async def ensure_greeting(self, call_id):
        while True:
            if self.is_connection_made:
                asyncio.ensure_future(
                    self.sip_sessions[call_id].greeting(self.transport)
                )
                break
            await asyncio.sleep(SLEEP_TIME)
