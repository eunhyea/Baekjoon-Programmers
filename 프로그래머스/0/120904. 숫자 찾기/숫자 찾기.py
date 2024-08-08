def solution(num, k):
    num = str(num)
    k = str(k)
    
    if k in num:
        return num.index(k)+1
    else : 
        return -1