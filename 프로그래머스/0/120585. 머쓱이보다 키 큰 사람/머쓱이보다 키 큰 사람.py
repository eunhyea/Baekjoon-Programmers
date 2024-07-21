def solution(array, height):
    result = 0
    for i in array:
        if i > height:
            result += 1
    return result