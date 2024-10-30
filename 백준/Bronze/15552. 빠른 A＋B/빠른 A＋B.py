import sys

input = lambda: sys.stdin.readline().rstrip()
t = int(input())

results = []

for _ in range(t):
    a,b = map(int, input().split())
    results.append(a+b)

sys.stdout.write('\n'.join(map(str, results)))