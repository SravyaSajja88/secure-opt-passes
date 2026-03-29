
#include <stdio.h>
#include <stdlib.h>

int array_sum(int *arr, int size, int start, int end) {
  // Bounds checks
  if (start < 0 || start >= size)
    abort();
  if (end < 0 || end > size)
    abort();
  if (start > end)
    abort();

  int sum = 0;
  for (int i = start; i < end; i++) {
    sum += arr[i];
  }
  return sum;
}

int main() {
  int arr[10];
  for (int i = 0; i < 10; i++) {
    arr[i] = i + 47;
  }

  int result = array_sum(arr, 10, 2, 9);
  printf("Sum: %d\n", result);
  return 0;
}

void dummy_func_0() {
  int a = 65;
  if (a < 0)
    abort();
}
