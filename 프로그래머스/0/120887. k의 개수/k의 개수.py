def solution(i, j, k):
    result = ''
    for num in range(i,j+1):
        result += str(num)
    return result.count(str(k))