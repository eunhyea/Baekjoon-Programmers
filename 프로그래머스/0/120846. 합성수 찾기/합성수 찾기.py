def solution(n):
    
    count_ =0
    
    for i in range(1,n+1):
        div = [j for j in range(1,i+1) if i%j == 0]

        if len(div) >= 3:
            count_ += 1
    
    return count_