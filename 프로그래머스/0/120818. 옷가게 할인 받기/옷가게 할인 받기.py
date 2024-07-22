def solution(price):
    if price < 100000:
        return price
    elif price < 300000:
        return int(price*(1-0.05))
    elif price < 500000:
        return int(price*(1-0.1))
    else : return int(price*(1-0.2))