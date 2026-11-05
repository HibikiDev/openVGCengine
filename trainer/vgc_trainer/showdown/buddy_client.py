













from __future__ import annotations

import asyncio
import ipaddress
import logging

import websockets

from .battle import USER_AGENT, VERSION, BaseClient
from .sheets import BUDDY_SUFFIX
from .teams import pack
from .tracker import to_id

log = logging.getLogger("showdown")



class NotLoopback(RuntimeError):
    pass


class BuddyClient(BaseClient):



    def __init__(self, port: int, username: str, agent, team: list[dict], fmt: str = "gen9championsvgc2026regmcbuddy",
                 formats: list[str] | None = None, allow: set[str] | None = None):
        port = int(port)
        if not 0 < port < 65536:
            raise ValueError(f"not a port: {port}")
        formats = list(formats or [fmt])
        bad = [f for f in [fmt, *formats] if not f.endswith(BUDDY_SUFFIX)]
        if bad:
            raise ValueError(f"the buddy plays only the buddy formats (<format>{BUDDY_SUFFIX}): {bad}")
        super().__init__(f"ws://127.0.0.1:{port}/showdown/websocket", username, agent, team, fmt, formats)
        self.allow = {to_id(u) for u in (allow or ())}

    async def connect(self) -> None:
        self.ws = await websockets.connect(self.url, max_size=None, ping_interval=20, ping_timeout=60, proxy=None,
                                           user_agent_header=USER_AGENT)
        try:
            check_loopback(self.ws.remote_address)
        except NotLoopback:
            await self.ws.close()
            raise
        self.inbox: asyncio.Queue = asyncio.Queue()
        asyncio.get_running_loop().create_task(self._receiver())
        asyncio.get_running_loop().create_task(self._reader())
        await self.logged_in.wait()

    def accepts_format(self, fmt: str) -> bool:
        return fmt.partition("@@@")[0].endswith(BUDDY_SUFFIX) and super().accepts_format(fmt)

    async def accept_one(self, timeout: float | None = None):
        while True:
            user, _ = await asyncio.wait_for(self.challenges.get(), timeout)
            if not self.allow or to_id(user) in self.allow:
                break
            log.info("%s: declined a challenge from %s (not on the Buddy page's list)", self.username, user)
            await self.send(f"|/reject {user}")
        self.started = True
        self.last_popup = ""
        await self.send(f"|/utm {pack(self.team)}")
        await self.send(f"|/accept {user}")
        try:
            return await asyncio.wait_for(self.new_battle.get(), 30)
        except asyncio.TimeoutError:
            raise RuntimeError(f"accepting {user} didn't start a battle: {self.last_popup or 'no reply'}") from None

    def choice_text(self, choice: str) -> str:
        return choice.replace(", ", " , ")


def check_loopback(peer) -> None:


    host = peer[0] if peer else ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise NotLoopback(f"not an address: {host!r}") from None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_loopback:
        raise NotLoopback(f"the buddy plays only on this machine; the server is at {host}")
