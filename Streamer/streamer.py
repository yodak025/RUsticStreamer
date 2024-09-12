#!/usr/bin/python3

import argparse
import asyncio
import json
import os
import random

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer
from RusticSipClasses import RusticUdpProtocol, RusticSipProtocol

ROOT = os.path.dirname(__file__)

IP = '127.0.0.1'
PORT = random.randint(1024, 49151)
ADDRESS_STR = IP + ":" + str(PORT)

SIG_IP = '127.0.0.1'
SIG_PORT = 5060
SIG_ADDR_STR = SIG_IP + ":" + str(SIG_PORT)

VIDEO_TO_SERVE = "WORK.mp4"

SERVE_TIME = 3600

pcs = set()


def create_local_tracks(play_from, decode):
    player = MediaPlayer(play_from, decode=decode)
    return player.audio, player.video


async def run_answer(pc, offer_json):
    decode = True

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    audio, video = create_local_tracks(ROOT + "/" + VIDEO_TO_SERVE, decode=decode)
    if audio:
        pc.addTrack(audio)

    if video:
        pc.addTrack(video)

    while True:
        try:
            obj = RTCSessionDescription(**json.loads(offer_json))
        except json.JSONDecodeError:
            obj = None

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)

            if obj.type == "offer":
                await pc.setLocalDescription(await pc.createAnswer())
                return json.dumps({'sdp': pc.localDescription.sdp,
                                   'type': pc.localDescription.type
                                   })


class StreamerUDP(RusticUdpProtocol):
    pass


class StreamerSIP(RusticSipProtocol):
    def __init__(self, _address, _name, call_id=None):
        super().__init__(_address, _name, call_id)
        self.pc = RTCPeerConnection()

    async def greeting(self, transport, addr=None):
        self.register(SIG_ADDR_STR, VIDEO_TO_SERVE)

        await self.send_secure_sip_message(self.generate_message("send"), transport, [SIG_IP, SIG_PORT])

    async def response(self, data, address, transport):
        if data.type == "INVITE":

            body = await run_answer(self.pc, data.body)

            self.via_address = data.sip_addr["via"]
            self.call_id = data.call_id
            self.accepted_202(data.sip_addr["from"], body)

            message = self.generate_message("answer")
            await self.send_secure_sip_message(message, transport, data.via_addr)

        elif data.type == "ACK":
            self._received = True

        elif data.type == "BYE":
            pass

        elif data.type == "200 OK":
            self._received = True

        elif data.type == "403 Forbidden":
            await self.greeting(transport)

        else:
            pass


def parse_args():
    global VIDEO_TO_SERVE, SIG_IP, SIG_PORT, SIG_ADDR_STR

    parser = argparse.ArgumentParser(description="Front")
    parser.add_argument("video_file", type=str, default=VIDEO_TO_SERVE, help="Streaming video file")
    parser.add_argument("ip", type=str, default=SIG_IP, help="Signalling IP address")
    parser.add_argument("port", type=int, default=SIG_PORT, help="Signalling port")

    arguments = parser.parse_args()

    VIDEO_TO_SERVE = arguments.video_file

    SIG_IP = arguments.ip
    SIG_PORT = arguments.port
    SIG_ADDR_STR = f"{SIG_IP}:{SIG_PORT}"


async def main():
    parse_args()

    udp_connection = StreamerUDP([IP, PORT], StreamerSIP)

    streamer_session_call_id = udp_connection.create_sip_session(VIDEO_TO_SERVE)

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: udp_connection,
        local_addr=(IP, PORT))

    await udp_connection.ensure_greeting(streamer_session_call_id)

    try:
        await asyncio.sleep(SERVE_TIME)
    except KeyboardInterrupt:
        pass
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
