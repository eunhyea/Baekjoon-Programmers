def solution(balls, share):
    def factorial(number):
        if number == 1:
            return 1
        return number*factorial(number-1)
    
    def combination(n, m):
        a = n
        for _ in range(m-1):
            n -= 1
            a *= n            
        
        b = m
        for _ in range(m-2):
            m -= 1
            b *= m
        
        return a/b
    
    answer = combination(balls, share)
    return int(answer)