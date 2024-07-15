h, m = map(int, input('').split(' '))
cook = int(input(''))

cook_m = (m + cook) % 60
cook_h = ((m + cook) // 60) + h

if cook_h > 23 :
    print(f'{cook_h-24} {cook_m}')
else : 
    print(f'{cook_h} {cook_m}')