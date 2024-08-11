def solution(my_string):
    
    my_li = []
    
    for i in my_string:
        if i not in my_li:
            my_li.append(i)
    
    return ''.join(my_li)