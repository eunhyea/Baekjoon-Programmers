def solution(n):
    answer = 0
    for chr in str(n):
        answer += int(chr)
    return answer
