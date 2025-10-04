def solution(sizes):
    w_set = set()
    h_set = set()
    for w,h in sizes:
        w_set.add(min(w,h))
        h_set.add(max(w,h))
    answer = max(w_set)*max(h_set)
    return answer