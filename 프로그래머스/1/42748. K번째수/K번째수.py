def solution(array, commands):
    answer = []
    for s,e,cnt in commands:
        print(s,e,cnt)
        answer.append(sorted(array[s-1:e])[cnt-1])
    return answer