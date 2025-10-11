def solution(bin1, bin2):
    answer = ""
    extra_plus = 0
    max_len = max(len(bin1), len(bin2))

    def sum_2(numbers):
        numbers = [int(i) for i in numbers]
        if sum(numbers) == 0:
            tmp = 0
            extra_plus = 0
        if sum(numbers) == 1:
            tmp = 1
            extra_plus = 0
        if sum(numbers) == 2:
            tmp = 0
            extra_plus = 1
        if sum(numbers) == 3:
            tmp = 1
            extra_plus = 1
        return tmp, extra_plus
    
    for i in range(-1,-max_len-1, -1):
        if len(bin1) < -i:
            tmp, extra_plus = sum_2([bin2[i], extra_plus])
            answer = str(tmp) + answer
            continue
        if len(bin2) < -i:
            tmp, extra_plus = sum_2([bin1[i], extra_plus])
            answer = str(tmp) + answer
            continue
        tmp, extra_plus = sum_2([bin1[i], bin2[i], extra_plus])
        answer = str(tmp) + answer
    
    if extra_plus:
        answer = str(extra_plus) + answer
    return answer