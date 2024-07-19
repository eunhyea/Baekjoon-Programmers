# Read the number of elements
n = int(input())

# Collect all input elements
li = [int(input()) for _ in range(n)]

# Sort the list once
li.sort()

# Print sorted elements
for element in li:
    print(element)
