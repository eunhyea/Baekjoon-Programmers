def solution(n):
    answer = set()
    divisor = 1
    
    while divisor <= n/divisor:

        if n%divisor == 0:
            answer.add(divisor), 
            answer.add(n//divisor)

        divisor += 1
    return sorted(answer)