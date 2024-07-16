#1
T = int(input())
results = []

for i in range(T):
    A, B = map(int, input().split())
    results.append(A + B)

for result in results:
    print(result)

#2
T= int(input())
li=[]

for i in range(T):
  li.append(list(map(int,input().split())))

for i in range(len(li)):
  print(sum(li[i]))
