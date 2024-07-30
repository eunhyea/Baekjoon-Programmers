def solution(array):
    max_ = sorted(array)[-1]
    return [max_, array.index(max_)]