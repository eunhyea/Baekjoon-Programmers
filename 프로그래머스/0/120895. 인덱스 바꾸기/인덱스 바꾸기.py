def solution(my_string, num1, num2):
    my_strli = list(my_string)
    my_strli[num1], my_strli[num2] = my_strli[num2], my_strli[num1]
    return ''.join(my_strli)