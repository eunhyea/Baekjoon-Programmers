def solution(emergency):
    sorted_e = sorted(emergency, reverse=True) 
        
    return [sorted_e.index(i)+1 for i in emergency]