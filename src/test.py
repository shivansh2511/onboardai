# test.py
MY_CONST: str = "Hello"

def test_func(x: int) -> int:
    """Test function."""
    local_var = x * 2
    print(f"Result: {local_var}")
    return local_var