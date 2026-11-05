



import asyncio
import inspect

import pytest

from vgc_trainer.showdown import buddy_client as bc
from vgc_trainer.showdown.agent import Agent


@pytest.mark.parametrize("peer", [("127.0.0.1", 8000), ("127.5.6.7", 1), ("::1", 8000, 0, 0), ("::ffff:127.0.0.1", 8000, 0, 0)])
def test_loopback_peers_pass(peer):
    bc.check_loopback(peer)


@pytest.mark.parametrize("peer", [("8.8.8.8", 443), ("192.168.1.5", 8000), ("::ffff:8.8.8.8", 443, 0, 0), ("2606:4700::1", 443, 0, 0),
                                  ("sim3.psim.us", 443), None, ()])
def test_other_peers_refused(peer):
    with pytest.raises(bc.NotLoopback):
        bc.check_loopback(peer)


def test_no_url_argument():
    params = inspect.signature(bc.BuddyClient.__init__).parameters
    assert "url" not in params and "port" in params


def _client(**kw):
    async def mk():
        return bc.BuddyClient(8000, "BuddyTest", Agent("random"), [], **kw)
    return asyncio.run(mk())


def test_url_is_built_from_the_port():
    assert _client().url == "ws://127.0.0.1:8000/showdown/websocket"
    with pytest.raises(ValueError):
        _client_port("8000/../evil")


def _client_port(port):
    async def mk():
        return bc.BuddyClient(port, "BuddyTest", Agent("random"), [])
    return asyncio.run(mk())


def test_buddy_formats_only():
    with pytest.raises(ValueError):
        _client(fmt="gen9championsvgc2026regmc")
    c = _client(formats=["gen9championsvgc2026regmcbuddy", "gen5vgc2013buddy"])
    assert c.accepts_format("gen5vgc2013buddy") and c.accepts_format("gen5vgc2013buddy@@@Best Of = 3")
    assert not c.accepts_format("gen5vgc2013") and not c.accepts_format("gen9championsvgc2026regmc")


def test_choice_shape():
    c = _client()
    assert c.choice_text("move 1 2, move 2 1") == "move 1 2 , move 2 1"
    assert c.choice_text("team 1234") == "team 1234"


def test_a_remote_peer_is_closed_before_anything_is_sent(monkeypatch):
    sent, closed = [], []

    class FakeWS:
        remote_address = ("8.8.8.8", 443)

        async def send(self, msg):
            sent.append(msg)

        async def close(self):
            closed.append(True)

    async def fake_connect(url, **kw):
        assert kw.get("proxy", "unset") is None and kw.get("user_agent_header", "").endswith(f"openVGCengine-buddy/{bc.VERSION}")
        return FakeWS()

    monkeypatch.setattr(bc.websockets, "connect", fake_connect)
    c = _client()
    with pytest.raises(bc.NotLoopback):
        asyncio.run(asyncio.wait_for(c.connect(), 5))
    assert closed and not sent
