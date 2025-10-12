def solution(progresses, speeds):
    answer = []
    cnt = 1

    ddays = [0] * len(progresses)
    for idx, (p, s) in enumerate(zip(progresses, speeds)):
        ddays[idx] = (100 - p) // s
        if (100 - p) % s > 0 :
            ddays[idx] += 1
    
    stacked = ddays.pop(0)
    for d in ddays:
        if stacked >= d:
            cnt += 1
        else :
            answer.append(cnt)
            cnt = 1
            stacked = d
    answer.append(cnt)
    return answer