TIER = {"vip": 0.25, "gold": 0.15, "silver": 0.08}

FLOOR = 5.0


def checkout(items, discount, tier="silver"):
    base = 0
    for it in items:
        base += it
    if tier in TIER:
        base *= 1.0 - TIER[tier]
    if discount > 0:
        base -= base * discount
    if base < FLOOR:
        base = FLOOR
    total = round(base, 2)
    return total
