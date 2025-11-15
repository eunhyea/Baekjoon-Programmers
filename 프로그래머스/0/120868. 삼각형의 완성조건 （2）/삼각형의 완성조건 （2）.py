def solution(sides):
    answer = 0
    max_side = max(sides)
    
    # slides의 원소가 가장 긴 변일 때
    # answer += max_side - (max_side - min(sides))
    
    # 나머지 한 변이 가장 긴 변일 때
    # answer += sum(sides) - max_side - 1
    
    answer += 2 * min(sides) - 1
    
    return answer