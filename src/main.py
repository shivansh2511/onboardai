# src/main.py
import os
from .code_analyzer import CodeAnalyzer
from typing import Optional 
from src.database.sqlite_manager import SQLiteManager # <--- ADDED: Import SQLiteManager
import datetime # <--- ADDED: Import datetime for getting current time

def main():
    print("Starting OnboardAI MVP Demo...")

    # --- NEW: Initialize and connect to SQLite Database ---
    db_manager = SQLiteManager()
    db_manager.connect()
    db_manager.create_tables() # Ensure tables exist

    # Example Python code to analyze (your provided example)
    python_code_example = """
# This is a sample module
global_var_1 = "I am global"
GLOBAL_CONST: int = 100

def greet(name: str = "World", greeting: Optional[str] = None):
    \"\"\"
    Greets the given name with an optional greeting.
    \"\"\"
    local_msg = "A message" # Local variable
    if greeting:
        print(f"{greeting}, {name}!") # Calls 'print'
    else:
        default_greeting_val = "Hello" # Another local variable
        print(f"{default_greeting_val}, {name}!") # Calls 'print'

class Calculator:
    \"\"\"
    A simple calculator class for basic arithmetic.
    \"\"\"
    class_attr = "I am a class attribute"
    ANOTHER_ATTR: float = 3.14

    def __init__(self, initial_value: int = 0):
        \"\"\"
        Initializes the Calculator with a starting value.
        \"\"\"
        self.value = initial_value # Instance attribute
        init_local_var = "initialized"
        print("Calculator initialized!") # Calls 'print'

    def add(self, a: int, b: int) -> int:
        \"\"\"
        Adds two numbers and returns the sum.
        \"\"\"
        sum_result: int = a + b # Local variable with type annotation
        temp_var = 5
        self.log_operation(f"Adding {a} and {b}") # Calls a method within the class
        return sum_result

    def log_operation(self, message: str):
        print(f"[LOG]: {message}") # Calls 'print'

def goodbye(name: str):
    \"\"\"Says goodbye to the given name.\"\"\"
    farewell_message = f"Goodbye, {name}!"
    print(farewell_message) # Calls 'print'
    greet("User") # Calls another top-level function
    calc = Calculator(10) # Instantiates Calculator, which calls __init__ indirectly. Direct call to Calculator class.
    result = calc.add(5, 7) # Calls a method of an instantiated object
    print(f"Calculation result: {result}") # Calls 'print'
    """

    # Get the absolute path for the file we are analyzing
    # For a real project, you would iterate over actual files.
    # Here, we simulate a file path for the example code.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    example_file_path = os.path.join(script_dir, 'example_code_to_analyze.py')
    
    # Initialize the CodeAnalyzer for Python and pass the db_manager
    python_analyzer = CodeAnalyzer(language_name="python", db_manager=db_manager) # <--- MODIFIED: Pass db_manager

    # Analyze the example code using the class's method
    print("\n--- Analyzing Sample Python Code ---")
    analysis_results = python_analyzer.analyze_code(python_code_example, file_path=example_file_path) # <--- MODIFIED: Pass file_path

    if analysis_results:
        print("\n--- OnboardAI Analysis Summary ---")
        # Existing print statements (no change here)
        print(f"Module Docstring: N/A (Feature to be implemented)") 
        print(f"Top-Level Variables: {[v.name for v in analysis_results.get('top_level_variables', [])]}")
        print(f"Functions Found: {[f.name for f in analysis_results.get('functions', [])]}")
        print(f"Classes Found: {[c.name for c in analysis_results.get('classes', [])]}")

        print("\nDetailed Functions:")
        for func in analysis_results.get('functions', []):
            print(f"  - Function: {func.name} (Lines {func.start_line}-{func.end_line})")
            if func.docstring:
                print(f"    Docstring: {func.docstring[:50]}...")
            if func.variables:
                print(f"    Local Vars: {[lv.name for lv in func.variables]}")
            if func.calls_made:
                print(f"    Calls: {func.calls_made}")


        print("\nDetailed Classes:")
        for cls in analysis_results.get('classes', []):
            print(f"  - Class: {cls.name} (Lines {cls.start_line}-{cls.end_line})")
            if cls.docstring:
                print(f"    Docstring: {cls.docstring[:50]}...")
            if cls.attributes:
                print(f"    Class Attributes: {[ca.name for ca in cls.attributes]}")
            if cls.methods:
                print(f"    Methods: {[m.name for m in cls.methods]}")
                for method in cls.methods:
                    if method.calls_made:
                        print(f"      - Method {method.name} Calls: {method.calls_made}")


    else:
        print("Failed to analyze code.")

    print("\nOnboardAI MVP Demo Complete.")
    db_manager.close() # <--- NEW: Close database connection

if __name__ == "__main__":
    main()