from collections import Counter

def solution(answers):
    first = [1,2,3,4,5] * (10000//5)
    second = [2,1,2,3,2,4,2,5] * (10000//8 + 1)
    third = [3,3,1,1,2,2,4,4,5,5] * (10000//10)
    cnt = Counter({1:0,2:0,3:0})
    answer = []

    for i in range(len(answers)):    
        if answers[i] == first[i]:
            cnt[1] += 1
        if answers[i] == second[i]:
            cnt[2] += 1
        if answers[i] == third[i]:
            cnt[3] += 1
    
    max_score = max(cnt.values())
    for k,v in cnt.items():
        if v >= max_score:
            answer.append(k)
            
    return answer