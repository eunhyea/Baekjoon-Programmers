def solution(sizes):
    max_long = 0 
    max_short = 0
    
    for w,h in sizes:
        long = max(w,h)
        short = min(w,h)
        
        if max_long < long:
            max_long = long
        if max_short < short:
            max_short = short
    answer = max_long * max_short
    return answer