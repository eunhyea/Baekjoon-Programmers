def solution(n):
    answer = []
    divisor = 1
    
    while divisor <= n/divisor:

        if n%divisor == 0:
            answer.extend({divisor, n//divisor})

        divisor += 1
    return sorted(answer)