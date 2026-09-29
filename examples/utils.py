import hashlib
import time

SALT = "demo-salt-v1"


def make_token(user, total):
    raw = "%s|%.2f|%d" % (user, total, int(time.time() // 60))
    return hashlib.sha256((SALT + raw).encode("utf-8")).hexdigest()[:16]


def render(token, total):
    return "[OK] token=%s total=%.2f" % (token, total)
