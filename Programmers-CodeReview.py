# 120803 lambda 사용하기
solution = lambda num1, num2 : num1 - num2

# 120807 return 값에도 조건 추가가 가능함
def solution(num1, num2):
    return 1 if num1==num2 else -1

# 입문/배열의 유사도 : set 자료형
# https://thirsty-hosta-2d1.notion.site/set-bb97fef22c954cee86f23f0fce23109b?pvs=4
# 내코드
import numpy
def solution(s1, s2):
    return len(s1) + len(s2) - len(set(s1+s2))
# 교집합 set1 & set2
def solution(s1, s2):
    return len(set(s1)&set(s2))

# 입문/점의 위치 구하기 : boolean 자료형 응용
def solution(dot):
    quad = [(3,2),(4,1)]
    return quad[dot[0] > 0][dot[1] > 0]

# 입문/피자 나눠먹기(3) : 올림 계산하기
def solution(slice, n):
    return ((n - 1) // slice) + 1
