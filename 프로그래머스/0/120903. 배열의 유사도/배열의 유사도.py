import numpy as np
def solution(s1, s2):
    return len(s1) + len(s2) - len(set(s1+s2))