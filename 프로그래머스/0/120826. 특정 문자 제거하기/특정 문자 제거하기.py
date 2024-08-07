import numpy
def solution(my_string, letter):
    rmletter = [i for i in my_string if i != letter]
    return ''.join(rmletter)