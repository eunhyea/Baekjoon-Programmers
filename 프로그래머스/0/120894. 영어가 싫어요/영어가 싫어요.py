def solution(numbers):
    to_num = {"zero":"0", "one":"1", "two":"2", "three":"3", "four":"4", "five":"5", "six":"6", "seven":"7", "eight":"8", "nine":"9"}
    answer = ""
    while len(numbers) > 0:
        for k,v in to_num.items():
            if numbers.startswith(k):
                answer += v
                numbers = numbers[len(k):]
    return int(answer)