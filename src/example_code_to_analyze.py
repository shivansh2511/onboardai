# This is a sample module
global_var_1 = "I am global"
GLOBAL_CONST: int = 100

def greet(name: str, greeting: str = "Hello") -> str:
    """
    Greets the given name with an optional greeting message.
    
    Args:
        name: The name to greet.
        greeting: The greeting to use (defaults to "Hello").
    
    Returns:
        A greeting string.
    """
    message = f"{greeting}, {name}!"
    print(message)
    return message

class Calculator:
    """
    A simple calculator class for basic arithmetic operations.
    """
    def __init__(self, initial_value: int = 0):
        """
        Initialize the calculator with a starting value.
        """
        self.value = initial_value
        self.log_operation(f"Initialized with {initial_value}")

    def add(self, x: int) -> int:
        """
        Adds x to the current value.
        """
        self.value += x
        self.log_operation(f"Added {x}")
        return self.value

    def log_operation(self, message: str) -> None:
        """
        Logs an operation to the console.
        """
        print(f"[LOG] {message}")

def goodbye(name: str) -> str:
    """
    Says goodbye to the given name.
    """
    message = f"Goodbye, {name}!"
    print(message)
    return message