def solution(numbers, k):
    # k가 1씩 증가할 때 마다 idx는 1에서부터 += 2
    idx = (k*2-1) % len(numbers)
    if idx == 0:
        # numbers=[1,2,3], k=2와 같은 경우
        idx = len(numbers)
    return idx