def solution(n, lost, reserve):
    answer = 0
    cnt = {i:1 for i in range(1,n+1)}
    
    # 중복 제거
    for i in lost:
        cnt[i] -= 1
    for i in reserve:
        cnt[i] += 1
    
    for i in range(1,n+1):
        if cnt[i]==2:
            # 큰 수부터 검토
            if i-1 > 0 and cnt[i-1]==0:
                cnt[i]-=1
                cnt[i-1]+=1
            elif i+1 <= n and cnt[i+1]==0:
                cnt[i]-=1
                cnt[i+1]+=1
            # 이후 작은 수 검토


    for v in cnt.values():
        if v >= 1:
            answer += 1
    
    return answer