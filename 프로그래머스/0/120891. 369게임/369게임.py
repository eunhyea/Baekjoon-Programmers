def solution(order):
    count = 0
    
    for i in str(order):
        if i=='3' or i=='6' or i=='9':
            count += 1
    
    return count