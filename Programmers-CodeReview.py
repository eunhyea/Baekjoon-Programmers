# 120803 lambda 사용하기
solution = lambda num1, num2 : num1 - num2

# 120807 return 값에도 조건 추가가 가능함
def solution(num1, num2):
    return 1 if num1==num2 else -1

# set 자료형
# https://thirsty-hosta-2d1.notion.site/set-bb97fef22c954cee86f23f0fce23109b?pvs=4
# 내코드
import numpy
def solution(s1, s2):
    return len(s1) + len(s2) - len(set(s1+s2))
# 교집합 set1 & set2
def solution(s1, s2):
    return len(set(s1)&set(s2))
