#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>

int solution(int num, int n) {
    return (num % n == 0) ? 1 : 0;
}