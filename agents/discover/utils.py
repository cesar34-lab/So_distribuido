import math
from typing import Dict

def matches_required_tags(entry_tags: list, required_tags: dict) -> bool:
    """required_tags example: {'gpu': True} or {'arch': 'arm'}"""
    if not required_tags:
        return True
    for k, v in required_tags.items():
        # support boolean or string matching
        tag_val = None
        for t in entry_tags:
            if isinstance(t, str) and ':' in t:
                tk, tv = t.split(':', 1)
                if tk == k:
                    tag_val = tv
                    break
        if tag_val is None:
            return False
        # normalize
        if isinstance(v, bool):
            if str(tag_val).lower() not in ('true','false','1','0'):
                return False
            if (str(tag_val).lower() in ('true','1')) != v:
                return False
        else:
            if str(tag_val) != str(v):
                return False
    return True

def compute_score(entry, required_ram=0, required_tags=None):
    """
    Score = w1*(1 - cpu_load) + w2*reputation + w3*normalized_ram + w4*(1 - normalized_rtt) + tag_bonus
    """
    if required_tags is None:
        required_tags = {}
    w1, w2, w3, w4 = 0.4, 0.25, 0.2, 0.15
    load = 1.0 - float(entry.cpu_load)
    rep = float(entry.reputation)
    # normalized ram: ratio with cap at 1
    norm_ram = min(entry.ram_free_mb / max(1, required_ram), 1.0) if required_ram>0 else min(entry.ram_free_mb / 1024.0, 1.0)
    norm_rtt = 1.0 - min(entry.rtt_ms / 200.0, 1.0)
    tag_bonus = 0.2 if matches_required_tags(entry.tags, required_tags) else 0.0
    score = w1*load + w2*rep + w3*norm_ram + w4*norm_rtt + tag_bonus
    # clamp
    return max(0.0, min(1.0, score))
