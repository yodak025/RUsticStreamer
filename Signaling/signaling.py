#!/usr/bin/python3
import argparse
import asyncio
import os
import json
import xml.dom.minidom as dom

from RusticSipClasses import SLEEP_TIME, RusticUdpProtocol, RusticSipProtocol, RusticSipMessages, _line_log
from xml.parsers.expat import ExpatError


ROOT = os.path.dirname(__file__)

IP = '127.0.0.1'
PORT = 5060
ADDR_STR = IP + ":" + str(PORT)

SERVE_TIME = 3600


class DataBase:
    def __init__(self, file_path="data.xml"):
        self.__STATES__ = [
            "offer-received",
            "answer-received",
            "connection-established",
            "connection-error",
            "connection-finished"
        ]

        self.file_path = file_path
        self.data = self._load_data()
        self._save_data()

        self.root = self.data.documentElement
        self.streamers = self.root.getElementsByTagName("streamers")[0]
        self.connections = self.root.getElementsByTagName("sessions")[0]

    def _load_data(self):
        try:
            data = dom.parse(self.file_path)
        except (FileNotFoundError, ExpatError):
            data = dom.Document()
            data.appendChild(data.createElement("data-base"))
            database = data.getElementsByTagName("data-base")[0]
            database.appendChild(data.createElement("streamers"))
            database.appendChild(data.createElement("sessions"))

        return data

    def _save_data(self):
        with open(self.file_path, "w") as f:
            self.data.writexml(f)

    def _streamer_exists(self, streamer_msg):
        for streamer_element in self.streamers.getElementsByTagName("streamer"):
            if (
                streamer_element.getElementsByTagName(
                    "address")[0].firstChild.nodeValue == streamer_msg.sip_addr["from"]
            ):
                return True
        return False

    def add_streamer(self, streamer_msg):
        if self._streamer_exists(streamer_msg):
            return  # Evita agregar streamers duplicados

        new_streamer = self.data.createElement("streamer")

        address_element = self.data.createElement("address")
        address_element.appendChild(
            self.data.createTextNode(streamer_msg.sip_addr["from"])
        )
        new_streamer.appendChild(address_element)

        name_element = self.data.createElement("name")
        name_element.appendChild(self.data.createTextNode(streamer_msg.user_agent))
        new_streamer.appendChild(name_element)

        call_id_element = self.data.createElement("call_id")
        call_id_element.appendChild(self.data.createTextNode(streamer_msg.call_id))
        new_streamer.appendChild(call_id_element)

        info_element = self.data.createElement("info")
        image_element = self.data.createElement("image")
        description_element = self.data.createElement("description")
        image_element.appendChild(self.data.createTextNode(streamer_msg.body))  #
        description_element.appendChild(self.data.createTextNode(streamer_msg.body))
        info_element.appendChild(image_element)
        info_element.appendChild(description_element)
        new_streamer.appendChild(info_element)

        self.streamers.appendChild(new_streamer)
        self._save_data()

    def add_connection(self, front_msg):
        new_connection = self.data.createElement("session")

        addresses_element = self.data.createElement("addresses")
        front_address_element = self.data.createElement("front")
        streamer_address_element = self.data.createElement("streamer")
        front_address_element.appendChild(
            self.data.createTextNode(front_msg.sip_addr["from"])
        )
        streamer_address_element.appendChild(
            self.data.createTextNode(front_msg.sip_addr["to"])
        )
        addresses_element.appendChild(front_address_element)
        addresses_element.appendChild(streamer_address_element)
        new_connection.appendChild(addresses_element)

        name_element = self.data.createElement("name")
        name_element.appendChild(self.data.createTextNode(front_msg.user_agent))
        new_connection.appendChild(name_element)

        call_id_element = self.data.createElement("call_id")
        call_id_element.appendChild(self.data.createTextNode(front_msg.call_id))
        new_connection.appendChild(call_id_element)

        sdp_element = self.data.createElement("sdp")
        offer_element = self.data.createElement("offer")
        offer_element.appendChild(self.data.createTextNode("None"))
        answer_element = self.data.createElement("answer")
        answer_element.appendChild(self.data.createTextNode("None"))
        sdp_element.appendChild(offer_element)
        sdp_element.appendChild(answer_element)
        new_connection.appendChild(sdp_element)

        sdp_state = self.data.createElement("state")
        sdp_state.appendChild(self.data.createTextNode("offer-received"))
        new_connection.appendChild(sdp_state)

        self.root.appendChild(new_connection)
        self._save_data()

    def remove_streamer(self, call_id):
        for streamer_element in self.streamers.getElementsByTagName("streamer"):
            if streamer_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                self.streamers.removeChild(streamer_element)
                self._save_data()
                break
        return None

    def remove_connection(self, call_id):
        for connection_element in self.connections.getElementsByTagName("session"):
            if connection_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                self.connections.removeChild(connection_element)
                self._save_data()
                break
        return None

    def change_offer_answer(self, call_id, sig_data, sig_type: str):
        for connection_element in self.connections.getElementsByTagName("session"):
            if connection_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                sdp = connection_element.getElementsByTagName("sdp")[0]
                tag = sdp.getElementsByTagName(sig_type)[0]
                tag.firstChild.nodeValue = sig_data
                self._save_data()
        return None

    def change_state(self, call_id, new_state):
        if new_state in self.__STATES__:
            for connection_element in self.root.getElementsByTagName("session"):
                if connection_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                    state = connection_element.getElementsByTagName("state")[0]
                    state.firstChild.nodeValue = new_state
            self._save_data()
            return None
        else:
            return None

    def get_streamer_info(self):
        streamers = []
        for streamer_element in self.streamers.getElementsByTagName("streamer"):

            name = streamer_element.getElementsByTagName("name")[0].firstChild.nodeValue
            address = streamer_element.getElementsByTagName("address")[0].firstChild.nodeValue
            info = streamer_element.getElementsByTagName("info")[0]
            image = info.getElementsByTagName("image")[0].firstChild.nodeValue
            description = info.getElementsByTagName("description")[0].firstChild.nodeValue

            current_streamer = {
                "name": name,
                "address": address,
                "image": image,
                "description": description
            }

            streamers.append(current_streamer)

        if not streamers:
            return None

        options = json.dumps({
            "streamers": streamers
        })

        return options

    def get_offer_answer(self, call_id):
        for connection_element in self.connections.getElementsByTagName("session"):
            if connection_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                sdp = connection_element.getElementsByTagName("sdp")[0]
                offer = sdp.getElementsByTagName("offer")[0].firstChild.nodeValue
                answer = sdp.getElementsByTagName("answer")[0].firstChild.nodeValue

                return offer, answer

        return None

    def get_state(self, call_id):
        for connection_element in self.root.getElementsByTagName("session"):
            if connection_element.getElementsByTagName("call_id")[0].firstChild.nodeValue == call_id:
                state = connection_element.getElementsByTagName("state")[0]

                return state.firstChild.nodeValue

        return None

    def all_streamers_info(self):
        addresses = []
        call_ids = []
        names = []
        for streamer_element in self.streamers.getElementsByTagName("streamer"):
            address = streamer_element.getElementsByTagName("address")[0].firstChild.nodeValue
            addresses.append(address.split(":"))
            call_id = streamer_element.getElementsByTagName("call_id")[0].firstChild.nodeValue
            call_ids.append(call_id)
            name = streamer_element.getElementsByTagName("name")[0].firstChild.nodeValue
            names.append(name)

        return addresses, call_ids, names


class SignallingUDP(RusticUdpProtocol):

    async def load_database(self):
        db = DataBase(ROOT + "/data.xml")
        [_addresses, _call_ids, _names] = db.all_streamers_info()

        while True:
            if self.is_connection_made:
                for i in range(len(_addresses)):
                    db.remove_streamer(_call_ids[i])
                    self.create_sip_session(_names[i], _call_ids[i])
                    asyncio.ensure_future(
                        self.sip_sessions[_call_ids[i]].greeting(self.transport, _addresses[i])
                    )
                break
            await asyncio.sleep(SLEEP_TIME)

    def link_sip_session(self, from_address, name, call_id=None):
        new_call = self.protocol(
            from_address,
            name,
            call_id,
            self.address
        )

        key = new_call.call_id
        self.sip_sessions[key] = new_call
        return key

    def datagram_received(self, data, addr):
        message = RusticSipMessages(data)

        _line_log(message.type + ' ' + ' Send to: < sip:' + message.to_addr[0] + ':' + message.to_addr[1] + '>' +
                  '  From: < sip:' + message.from_addr[0] + ':' + message.from_addr[1] + '>')

        try:
            sip_session = self.sip_sessions[message.call_id]
        except KeyError:
            # Si no hay entrada en .sip_sessions, se crea una nueva llamada con el call_id del mensaje.
            if message.type == "REGISTER" or message.type == "OPTIONS":
                new_call_id = self.create_sip_session(message.user_agent, message.call_id)
            else:
                new_call_id = self.link_sip_session(message.from_addr, message.user_agent, message.call_id)

            sip_session = self.sip_sessions[new_call_id]

        asyncio.ensure_future(sip_session.response(message, addr, self.transport))


class SignallingSIP(RusticSipProtocol):

    def __init__(self, _from_address, _name, _call_id=None, _via_address=None):
        super().__init__(_from_address, _name, _call_id)

        if _via_address is not None:
            self.via_address = _via_address[0] + ":" + str(_via_address[1])

        self.db = DataBase(ROOT + "/data.xml")
        self.isUpdated = False
        global ADDR_STR

    async def send_secure_sip_message(self, msg, transport, direction):
        while True:
            state = self.db.get_state(self.call_id)
            if state == "answer-received" or state == "connection-established":
                break

            transport.sendto(msg.encode(), (direction[0], int(direction[1])))
            await asyncio.sleep(SLEEP_TIME)

    async def send_secure_sip_answer(self, msg, transport, direction):
        while True:
            state = self.db.get_state(self.call_id)
            if state == "connection-established":
                break

            transport.sendto(msg.encode(), (direction[0], int(direction[1])))
            await asyncio.sleep(SLEEP_TIME)

    async def greeting(self, transport, addr):
        destination = addr[0] + ":" + addr[1]
        self.forbidden_403(destination)

        self.send_sip_message(self.generate_message("answer"), transport, addr)

    async def response(self, data, address, transport):
        if data.type == "INVITE":
            # Actualizar sdp en la base de datos
            self.db.add_connection(data)

            # Mensaje de respuesta a front
            self.trying_100(data.sip_addr["from"])
            self.send_sip_message(self.generate_message("answer"), transport, data.from_addr)

            # Mensaje a streamer
            self.from_address = data.sip_addr["from"]
            self.via_address = data.sip_addr["via"]

            self.invite(data.sip_addr["to"], data.body)
            await self.send_secure_sip_message(self.generate_message("send"), transport, data.to_addr)

            self.db.change_offer_answer(data.call_id, data.body, "offer")

        elif data.type == "ACK":
            self.db.change_state(data.call_id, "connection-established")

        elif data.type == "BYE":
            self.db.change_state(data.call_id, "connection-finished")

        elif data.type == "REGISTER":
            self.db.add_streamer(data)

            self.ok_200(data.sip_addr["from"])
            self.send_sip_message(self.generate_message("answer"), transport, data.from_addr)

        elif data.type == "OPTIONS":
            body = self.db.get_streamer_info()
            if body is None:
                raise Exception("Error creating OPTIONS JSON answer")

            self.ok_200(data.sip_addr["from"], body)
            self.send_sip_message(self.generate_message("answer"), transport, data.from_addr)

        elif data.type == "202 Accepted":

            self.db.change_state(data.call_id, "answer-received")

            # Al streamer
            self.via_address = "****"
            self.from_address = data.sip_addr["via"]

            self.ack(data.sip_addr["from"])
            self.send_sip_message(self.generate_message("send"), transport, data.from_addr)     # Ojo con las pérdidas

            # Al front
            self.via_address = data.sip_addr["via"]
            self.from_address = data.sip_addr["from"]

            self.accepted_202(data.sip_addr["to"], data.body)
            await self.send_secure_sip_answer(self.generate_message("answer"), transport, data.to_addr)

            self.db.change_offer_answer(data.call_id, data.body, "answer")

        else:
            self.db.change_state(data.call_id, "connection-error")


def parse_args():
    global PORT, ADDR_STR
    parser = argparse.ArgumentParser(description="Front")

    parser.add_argument("port", type=int, default=PORT, help="Signalling port")
    arguments = parser.parse_args()

    PORT = arguments.port
    ADDR_STR = IP + ":" + str(PORT)


async def main():
    parse_args()

    sip_connection = SignallingUDP([IP, PORT], SignallingSIP)

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: sip_connection, local_addr=(IP, PORT))

    await sip_connection.load_database()

    try:
        await asyncio.sleep(SERVE_TIME)
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())

