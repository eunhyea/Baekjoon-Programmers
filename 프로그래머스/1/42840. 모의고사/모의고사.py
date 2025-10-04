from collections import Counter

def solution(answers):
    first = [1,2,3,4,5]
    second = [2,1,2,3,2,4,2,5]
    third = [3,3,1,1,2,2,4,4,5,5]
    score = [0,0,0]
    answer = []

    for idx, ans in enumerate(answers):    
        if ans == first[idx%len(first)]:
            score[0] += 1
        if ans == second[idx%len(second)]:
            score[1] += 1
        if ans == third[idx%len(third)]:
            score[2] += 1
    
    for idx, s in enumerate(score):
        if s == max(score):
            answer.append(idx+1)

    return answer