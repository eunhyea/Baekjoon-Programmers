def solution(before, after):
    before_list = [i for i in before]
    
    for i in after:
        if i in before_list:
            before_list.remove(i)
    
    if before_list == []:
        return 1
    else : return 0