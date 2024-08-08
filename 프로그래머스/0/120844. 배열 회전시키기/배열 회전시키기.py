def solution(numbers, direction):
    
    if direction == 'left':
        left = numbers.pop(0)
        numbers.append(left)
    else :
        right = numbers.pop(-1)
        numbers.insert(0, right)
    
    return numbers