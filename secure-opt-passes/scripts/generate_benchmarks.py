"""
Benchmark Program Generator
Creates C programs with security checks for testing
"""

import argparse
import os
import random
from pathlib import Path


PROGRAM_TEMPLATES = [
    # Array bounds checking
    """
#include <stdio.h>
#include <stdlib.h>

int main() {
    int arr[{size}];
    int idx;
    
    for (int i = 0; i < {size}; i++) {
        arr[i] = i * {multiplier};
    }
    
    scanf("%d", &idx);
    
    // Bounds check
    if (idx < 0 || idx >= {size}) {
        abort();
    }
    
    printf("Value: %d\\n", arr[idx]);
    return 0;
}
""",
    
    # Array sum with bounds check
    """
#include <stdio.h>
#include <stdlib.h>

int array_sum(int *arr, int size, int start, int end) {
    // Bounds checks
    if (start < 0 || start >= size) abort();
    if (end < 0 || end > size) abort();
    if (start > end) abort();
    
    int sum = 0;
    for (int i = start; i < end; i++) {
        sum += arr[i];
    }
    return sum;
}

int main() {
    int arr[{size}];
    for (int i = 0; i < {size}; i++) {
        arr[i] = i + {offset};
    }
    
    int result = array_sum(arr, {size}, {start}, {end});
    printf("Sum: %d\\n", result);
    return 0;
}
""",
    
    # Matrix operations with checks
    """
#include <stdio.h>
#include <stdlib.h>

#define ROWS {rows}
#define COLS {cols}

void matrix_multiply(int a[ROWS][COLS], int b[ROWS][COLS], int result[ROWS][COLS]) {
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            result[i][j] = 0;
            for (int k = 0; k < COLS; k++) {
                result[i][j] += a[i][k] * b[k][j];
            }
        }
    }
}

int get_element(int matrix[ROWS][COLS], int row, int col) {
    // Bounds checks
    if (row < 0 || row >= ROWS) abort();
    if (col < 0 || col >= COLS) abort();
    
    return matrix[row][col];
}

int main() {
    int a[ROWS][COLS], b[ROWS][COLS], result[ROWS][COLS];
    
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            a[i][j] = i + j;
            b[i][j] = i * j;
        }
    }
    
    matrix_multiply(a, b, result);
    
    int val = get_element(result, {test_row}, {test_col});
    printf("Result[{test_row}][{test_col}] = %d\\n", val);
    
    return 0;
}
""",
    
    # String operations with bounds
    """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void safe_copy(char *dest, const char *src, int dest_size) {
    int src_len = strlen(src);
    
    // Check bounds
    if (src_len >= dest_size) {
        abort();
    }
    
    strcpy(dest, src);
}

int main() {
    char buffer[{buffer_size}];
    const char *message = "{message}";
    
    safe_copy(buffer, message, {buffer_size});
    printf("Message: %s\\n", buffer);
    
    return 0;
}
""",
    
    # Loop with validation
    """
#include <stdio.h>
#include <stdlib.h>

int process_array(int *data, int size) {
    if (size <= 0 || size > {max_size}) {
        abort();
    }
    
    int result = 0;
    for (int i = 0; i < size; i++) {
        if (i < 0 || i >= size) abort();
        result += data[i] * {factor};
    }
    
    return result;
}

int main() {
    int data[{actual_size}];
    
    for (int i = 0; i < {actual_size}; i++) {
        data[i] = i % {modulo};
    }
    
    int result = process_array(data, {actual_size});
    printf("Result: %d\\n", result);
    
    return 0;
}
"""
]


def generate_program(template_idx: int = None, seed: int = None) -> str:
    """Generate a C program from template"""
    if seed is not None:
        random.seed(seed)
    
    if template_idx is None:
        template_idx = random.randint(0, len(PROGRAM_TEMPLATES) - 1)
    
    template = PROGRAM_TEMPLATES[template_idx]
    
    # Generate random parameters
    params = {
        'size': random.choice([10, 20, 50, 100]),
        'multiplier': random.randint(1, 10),
        'offset': random.randint(0, 50),
        'start': random.randint(0, 5),
        'end': random.randint(6, 15),
        'rows': random.choice([4, 8, 16]),
        'cols': random.choice([4, 8, 16]),
        'test_row': random.randint(0, 3),
        'test_col': random.randint(0, 3),
        'buffer_size': random.choice([64, 128, 256]),
        'message': "Hello from benchmark",
        'max_size': random.choice([100, 200, 500]),
        'actual_size': random.choice([10, 20, 50]),
        'factor': random.randint(1, 5),
        'modulo': random.choice([10, 100, 256]),
    }
    
    # Make sure test_row/col are within bounds
    params['test_row'] = min(params['test_row'], params['rows'] - 1)
    params['test_col'] = min(params['test_col'], params['cols'] - 1)
    params['end'] = min(params['end'], params['size'])
    
    return template.format(**params)


def generate_benchmarks(count: int, output_dir: str, seed: int = 42):
    """Generate multiple benchmark programs"""
    os.makedirs(output_dir, exist_ok=True)
    
    random.seed(seed)
    
    for i in range(count):
        template_idx = i % len(PROGRAM_TEMPLATES)
        program = generate_program(template_idx, seed=seed + i)
        
        filename = f"benchmark_{i:03d}.c"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(program)
        
        print(f"Generated: {filename}")
    
    print(f"\nGenerated {count} benchmark programs in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark C programs")
    parser.add_argument("--count", type=int, default=50,
                       help="Number of programs to generate (default: 50)")
    parser.add_argument("--output", default="data/benchmarks",
                       help="Output directory (default: data/benchmarks)")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    
    args = parser.parse_args()
    
    generate_benchmarks(args.count, args.output, args.seed)


if __name__ == "__main__":
    main()
