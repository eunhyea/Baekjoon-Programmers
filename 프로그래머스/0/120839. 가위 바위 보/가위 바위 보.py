def solution(rsp):
    win = []
    for chr in rsp:
        if chr == '2':
            win.append('0')
        elif chr == '0':
            win.append('5')
        elif chr == '5':
            win.append('2')
    return ''.join(win)