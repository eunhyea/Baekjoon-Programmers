# 2750
n = int(input())
li =[]
for i in range(1,n+1):
    li.append(int(input()))
for i in range(n):
    print(sorted(li)[i])