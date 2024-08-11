def solution(my_string):
    answer = ''
    
    for i in my_string:
        if i not in '0123456789':
            answer += ' '
        else :
            answer += i
    return sum(map(int,answer.split()))