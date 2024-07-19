#1000 map 함수 쓰기
a,b = map(int, input().split(' '))
print(a+b)

#10950 반복문에서 list.append() 쓰기
T = int(input())
results = []

for i in range(T):
    A, B = map(int, input().split())
    results.append(A + B)

for result in results:
    print(result)

#9498 if 조건은 순차적으로 평가됨
a = int(input(''))
if a >= 90:
    print('A')
elif a >= 80:
    print('B')
elif a >= 70:
    print('C')
elif a >= 60:
    print('D')
else:
    print('F')
