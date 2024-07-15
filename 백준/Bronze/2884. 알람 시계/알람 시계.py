h, m = map(int, input('').split(' '))

if h==0 and m<45 :
    print(f'23 {m+15}')
elif m >= 45 :
    print(f'{h} {m-45}')
else : 
    print(f'{h-1} {m+15}') 