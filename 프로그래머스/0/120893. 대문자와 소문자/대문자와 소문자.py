def solution(my_string):
    change = ''
    for i in my_string:
        if i.isupper() :
            change += i.lower()
        elif i.islower() :
            change += i.upper()
    return change
