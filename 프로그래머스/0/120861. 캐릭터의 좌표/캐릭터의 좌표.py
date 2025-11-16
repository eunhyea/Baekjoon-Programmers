def solution(keyinput, board):
    answer = [0,0]    

    max_x = board[0]//2
    max_y = board[1]//2
    
    for k in keyinput:
        if k == 'right':
            answer[0] += 1
        elif k == 'left':
            answer[0] -= 1
        elif k == 'up':
            answer[1] += 1
        elif k == 'down':
            answer[1] -= 1
        
        answer[0] = min(answer[0], max_x) if answer[0]>=0 else max(answer[0], -max_x)
        answer[1] = min(answer[1], max_y) if answer[1]>=0 else max(answer[1], -max_y)
    
    return answer