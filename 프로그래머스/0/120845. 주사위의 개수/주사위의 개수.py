def solution(box, n):
    w,d,h = box[0]//n, box[1]//n, box[2]//n
    return w*d*h