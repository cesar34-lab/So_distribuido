# tests/test_protocols.py

import time
from agents.protocols import (
    make_hello, make_estado, sign_msg_for_send,
    parse_message, validate_message,
    verify_message_hmac
)

def test_make_and_parse():
    h = make_hello("nodeA", ["DISCOVER","NET"], time.time())
    raw = h.to_bytes()
    msg = parse_message(raw)

    assert validate_message(msg)
    assert msg.type == "HELLO"
    assert msg.src == "nodeA"
    print("[OK] test_make_and_parse")

def test_sign_and_verify():
    key = b'secret-test-key'
    estado = make_estado("nodeA", 0.2, 512, 0.95, 12, ["gpu:false"], 0.8)
    signed = sign_msg_for_send(estado, key)

    assert signed.meta.get("signed") is True
    sig = signed.meta["signature"]
    ok = verify_message_hmac(key, signed.msg_id, signed.payload, sig)

    assert ok is True
    print("[OK] test_sign_and_verify")

if __name__ == "__main__":
    test_make_and_parse()
    test_sign_and_verify()
    print("\n✅ All protocol tests passed!\n")
