# agents/net/transport.py
import asyncio
import json
import time
import uuid
import hmac
import hashlib
from typing import Dict, Any, Optional, Tuple

DEFAULT_ACK_TIMEOUT = 1.0  # segundos
DEFAULT_MAX_RETRIES = 5

class MessageRecord:
    def __init__(self, msg_id: str, packed: bytes, dst: Tuple[str,int],
                 reliable: bool, timestamp: float, retries: int=0, qos: str='DATA'):
        self.msg_id = msg_id
        self.packed = packed
        self.dst = dst
        self.reliable = reliable
        self.timestamp = timestamp
        self.retries = retries
        self.qos = qos

class SimpleSigner:
    def __init__(self, key: Optional[bytes]=None):
        self.key = key
    def sign(self, data: bytes) -> str:
        if not self.key:
            return ''
        mac = hmac.new(self.key, data, hashlib.sha256).hexdigest()
        return mac
    def verify(self, data: bytes, mac: str) -> bool:
        if not self.key:
            return True
        expected = hmac.new(self.key, data, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, mac)

def make_msg(msg_type: str, src: str, dst: str, payload: Any, msg_id: Optional[str]=None) -> Dict[str,Any]:
    if msg_id is None:
        msg_id = str(uuid.uuid4())
    return {
        "magic":"SOD1",
        "type": msg_type,
        "src": src,
        "dst": dst,
        "msg_id": msg_id,
        "timestamp": time.time(),
        "payload": payload
    }

def pack_msg(msg: Dict[str,Any], signer: Optional[SimpleSigner]=None) -> bytes:
    b = json.dumps(msg, separators=(',',':')).encode('utf-8')
    mac = ''
    if signer:
        mac = signer.sign(b)
    wrapper = {
        "meta": {
            "mac": mac
        },
        "data": b.decode('utf-8')
    }
    return json.dumps(wrapper, separators=(',',':')).encode('utf-8')

def unpack_msg(raw: bytes, signer: Optional[SimpleSigner]=None) -> Tuple[Dict[str,Any], bool]:
    """Devuelve (msg_dict, verified_bool)"""
    outer = json.loads(raw.decode('utf-8'))
    mac = outer.get('meta',{}).get('mac','')
    data = outer.get('data','').encode('utf-8')
    verified = True
    if signer:
        verified = signer.verify(data, mac)
    msg = json.loads(data.decode('utf-8'))
    return msg, verified
