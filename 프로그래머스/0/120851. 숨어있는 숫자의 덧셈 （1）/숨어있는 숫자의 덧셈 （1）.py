import re
def solution(my_string):
    nums = [i for i in my_string if re.match(r'^[1-9]$', i)]
    return sum(list(map(int,nums)))