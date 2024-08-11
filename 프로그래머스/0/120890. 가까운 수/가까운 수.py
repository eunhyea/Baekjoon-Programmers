def solution(array, n):
    
    if n in array:
        return n
    
    n_close = abs(max([i-n if i-n < 0 else -101 for i in array ]))
    p_close = abs(min([i-n if i-n > 0 else 101 for i in array ]))
        
    # n다 작은 가까운 값
    if n_close <= p_close:
        return n-n_close

    # n보다 큰 가까운 값
    if n_close > p_close:
        return n+p_close

# sort에서 key인자 여러 개로 정렬하기
def solution(array, n):
    array.sort(key=lambda x: (abs(x-n), x))
    return arrar[0]
