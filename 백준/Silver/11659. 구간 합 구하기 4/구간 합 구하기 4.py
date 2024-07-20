n, m = map(int, input().split())
li = list(map(int, input().split()))


# 순차적인 합 배열 만들기
pre_sum = [0] * (n+1) #초기화
for i in range(1,n+1):
    pre_sum[i] = pre_sum[i-1] + li[i-1]

# 구간합 구하기
result = []
for i in range(m):
    x, y = map(int, input().split())
    result.append(pre_sum[y] - pre_sum[x-1])

for i in result:
    print(i)