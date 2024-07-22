def solution(hp):
    if hp % 5 == 0:
        return hp // 5
    elif (hp % 5 == 1) or (hp % 5 == 3):
        return (hp//5)+1
    elif (hp % 5 == 2) or (hp % 5 == 4):
        return (hp//5)+2
