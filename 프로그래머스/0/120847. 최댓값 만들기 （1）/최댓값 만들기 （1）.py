def solution(numbers):
    a,b = sorted(numbers, reverse=True)[0:2]
    return a*b