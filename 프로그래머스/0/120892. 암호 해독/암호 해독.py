def solution(cipher, code):
    return ''.join([i for i in cipher[code-1::code]])