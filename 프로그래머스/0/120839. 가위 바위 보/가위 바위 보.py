def solution(rsp):
    win = {'0':'5', '2':'0', '5':'2'}
    answer = [win[chr] for chr in rsp]
    return ''.join(answer)