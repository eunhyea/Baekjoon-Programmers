def solution(my_string, n):
    answer = ''
    for chr in my_string:
        answer += chr*n
    return answer