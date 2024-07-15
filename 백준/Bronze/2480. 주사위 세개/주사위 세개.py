a, b, c = map(int, input('').split(' '))

if a==b and b==c :
    print(10000+a*1000)
elif a!=b and a!=c and b!=c :
    print(max(a,b,c)*100)
elif a==b :
    print(1000+100*a)
else :
    print(1000+100*c)