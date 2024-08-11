def solution(array, n):
    
    # n이 array에 포함될 때
    if n in array :
        return n
    
    n_close = abs(max([i-n if i-n < 0 else -101 for i in array]))
    p_close = abs(min([i-n if i-n > 0 else 101 for i in array]))
        
    # n보다 작은 가까운 값
    if n_close <= p_close:
        return n-n_close

    # n보다 큰 가까운 값
    if n_close > p_close:
        return n+p_close
