"""EricCode 测试配置和共享fixtures"""
import pytest
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_python_code():
    """示例Python代码"""
    return '''
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

class DataProcessor:
    def __init__(self, data):
        self.data = data
    
    def process(self):
        return [x * 2 for x in self.data]
    
    async def async_process(self):
        import asyncio
        await asyncio.sleep(0.1)
        return self.process()
'''


@pytest.fixture
def sample_javascript_code():
    """示例JavaScript代码"""
    return '''
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

class UserService {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.users = new Map();
    }
    
    async fetchUser(id) {
        const response = await this.apiClient.get(`/users/${id}`);
        this.users.set(id, response.data);
        return response.data;
    }
}
'''


@pytest.fixture
def sample_go_code():
    """示例Go代码"""
    return '''
package main

import "fmt"

func main() {
    numbers := []int{5, 3, 8, 1, 9}
    sorted := bubbleSort(numbers)
    fmt.Println(sorted)
}

func bubbleSort(arr []int) []int {
    n := len(arr)
    for i := 0; i < n-1; i++ {
        for j := 0; j < n-i-1; j++ {
            if arr[j] > arr[j+1] {
                arr[j], arr[j+1] = arr[j+1], arr[j]
            }
        }
    }
    return arr
}
'''


@pytest.fixture
def temp_file(tmp_path):
    """创建临时文件的fixture"""
    def _create_temp_file(content: str, suffix: str = ".py") -> Path:
        file_path = tmp_path / f"test_{id(content)}{suffix}"
        file_path.write_text(content, encoding="utf-8")
        return file_path
    return _create_temp_file
