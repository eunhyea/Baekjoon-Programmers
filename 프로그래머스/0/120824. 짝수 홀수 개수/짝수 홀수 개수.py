def solution(num_list):
    odd,even = 0,0
    
    for num in num_list:
        
        if num % 2 == 1:
            odd += 1
        else: even += 1
    
    return [even,odd]