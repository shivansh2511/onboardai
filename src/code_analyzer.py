from tree_sitter import Language, Parser, Tree, Node
import os
import tree_sitter_python as tspython # For loading the Python grammar
from dataclasses import dataclass, field
from typing import List, Optional

# --- Data Structures for Code Elements ---

@dataclass
class ParameterInfo:
    """Represents information about a function parameter."""
    name: str
    default_value: Optional[str] = None # For parameters like `param=None`
    type_annotation: Optional[str] = None # For parameters like `param: int`

@dataclass
class FunctionInfo:
    """Represents information about a function."""
    name: str
    start_line: int
    end_line: int
    parameters: List[ParameterInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    body: Optional[str] = None # The code content of the function body

@dataclass
class ClassInfo:
    """Represents information about a class."""
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    methods: List[FunctionInfo] = field(default_factory=list)
    body: Optional[str] = None # The code content of the class body

# --- Parser Setup (keep as is) ---

def initialize_python_parser() -> Parser:
    """
    Initializes and returns a Tree-sitter Parser for Python.
    Assumes tree-sitter-python package is installed.
    """
    try:
        PYTHON_LANGUAGE = Language(tspython.language())
        parser = Parser(PYTHON_LANGUAGE)
        print("Code Analyzer: Python Tree-sitter parser initialized.")
        return parser
    except Exception as e:
        print(f"Code Analyzer Error: Failed to initialize Python parser: {e}")
        print("Please ensure `tree-sitter-python` is installed and compatible.")
        raise


# --- Helper Functions for Extraction ---

def _extract_docstring(node: Node, code_string: bytes) -> Optional[str]:
    """Extracts the docstring from a function or class body node."""
    if node.type == 'expression_statement':
        string_node = node.child(0)
        if string_node and string_node.type == 'string':
            docstring_content = string_node.text.decode('utf8')
            if docstring_content.startswith('"""') and docstring_content.endswith('"""'):
                return docstring_content[3:-3].strip()
            elif docstring_content.startswith("'''") and docstring_content.endswith("'''"):
                return docstring_content[3:-3].strip()
            elif (docstring_content.startswith('"') and docstring_content.endswith('"')) or \
                 (docstring_content.startswith("'") and docstring_content.endswith("'")):
                 return docstring_content[1:-1].strip()
    return None

def _parse_single_parameter_node(param_node: Node, code_string: bytes) -> Optional[ParameterInfo]:
    """Recursively extracts information for a single parameter node."""
    if not param_node:
        return None

    name = None
    type_annotation = None
    default_value = None

    if param_node.type == 'identifier':
        name = param_node.text.decode('utf8')
    elif param_node.type == 'typed_parameter':
        # For typed_parameter, the name is typically the first named child
        name_node = None
        for child in param_node.named_children:
            if child.type == 'identifier': # The actual parameter name
                name_node = child
                break
        type_node = param_node.child_by_field_name('type') # This should consistently be accessible via field 'type'

        if name_node:
            name = name_node.text.decode('utf8')
        if type_node:
            type_annotation = type_node.text.decode('utf8')

    elif param_node.type == 'default_parameter':
        # The 'name' of a default_parameter can itself be a typed_parameter or identifier
        name_field_node = param_node.child_by_field_name('name')
        value_node = param_node.child_by_field_name('value')

        if value_node:
            default_value = value_node.text.decode('utf8')

        if name_field_node:
            # If the 'name' field is itself a typed_parameter, parse it recursively
            if name_field_node.type == 'typed_parameter':
                temp_param_info = _parse_single_parameter_node(name_field_node, code_string)
                if temp_param_info:
                    name = temp_param_info.name
                    type_annotation = temp_param_info.type_annotation
            elif name_field_node.type == 'identifier':
                name = name_field_node.text.decode('utf8')

    elif param_node.type == 'typed_default_parameter': # NEW HANDLER FOR THIS NODE TYPE
        name_node = None
        for child in param_node.named_children:
            if child.type == 'identifier': # The actual parameter name
                name_node = child
                break
        
        type_node = param_node.child_by_field_name('type')
        value_node = param_node.child_by_field_name('value')

        if name_node:
            name = name_node.text.decode('utf8')
        if type_node:
            type_annotation = type_node.text.decode('utf8')
        if value_node:
            default_value = value_node.text.decode('utf8')

    elif param_node.type == 'list_splat_pattern': # For *args
        name_node = param_node.child_by_field_name('name')
        if name_node:
            name = "*" + name_node.text.decode('utf8')
    elif param_node.type == 'dictionary_splat_pattern': # For **kwargs
        name_node = param_node.child_by_field_name('name')
        if name_node:
            name = "**" + name_node.text.decode('utf8')

    if name: # Only return if a name was successfully extracted
        return ParameterInfo(name=name, default_value=default_value, type_annotation=type_annotation)
    return None


def _extract_parameters(parameters_node: Node, code_string: bytes) -> List[ParameterInfo]:
    """Extracts parameter information from a 'parameters' node."""
    params: List[ParameterInfo] = []
    if not parameters_node or parameters_node.type != 'parameters':
        return params

    param_cursor = parameters_node.walk()
    if param_cursor.goto_first_child():
        while True:
            param_node = param_cursor.node
            
            # Skip punctuation and other non-parameter nodes (like newlines, indents, comments)
            if param_node.type not in [',', '(', ')', '_newline', '_indent', '_dedent', 'comment']: 
                param_info = _parse_single_parameter_node(param_node, code_string)
                if param_info:
                    params.append(param_info)

            if not param_cursor.goto_next_sibling():
                break
    return params

def _extract_body_content(node: Node, code_string: bytes) -> str:
    """Extracts the full code content of a node's body."""
    start_byte = node.start_byte
    end_byte = node.end_byte
    return code_string[start_byte:end_byte].decode('utf8')


# --- Main Analysis Function ---

def analyze_python_code(code_string: str, parser: Parser):
    """
    Parses Python code and extracts structured information about functions and classes.
    """
    print("\nCode Analyzer: Parsing code...")
    code_bytes = code_string.encode("utf8") # Encode once for consistency
    tree = parser.parse(code_bytes)
    
    # For debugging/confirmation, still print root node info
    print("Code Analyzer: AST Root Node Type:", tree.root_node.type)
    print("Code Analyzer: AST Root Node Text (first 100 chars):", tree.root_node.text.decode('utf8')[:100] + "...")

    functions: List[FunctionInfo] = []
    classes: List[ClassInfo] = []

    # Use a cursor to traverse the tree efficiently
    cursor = tree.walk()

    # Go to the first child of the root node (usually a module or compilation_unit)
    # and then iterate through its siblings (top-level definitions)
    if cursor.goto_first_child():
        while True:
            node = cursor.node
            
            # Get line numbers (Tree-sitter nodes are 0-indexed)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                parameters_node = node.child_by_field_name('parameters')
                body_node = node.child_by_field_name('body') # Get the function body node

                function_name = name_node.text.decode('utf8') if name_node else "Unnamed Function"
                
                # Extract parameters
                params_info = _extract_parameters(parameters_node, code_bytes)

                # Extract docstring from the beginning of the body
                docstring = None
                if body_node and body_node.child_count > 0:
                    first_child_of_body = body_node.child(0)
                    docstring = _extract_docstring(first_child_of_body, code_bytes)
                
                # Extract function body content
                function_body_content = _extract_body_content(body_node, code_bytes) if body_node else None


                func_info = FunctionInfo(
                    name=function_name,
                    start_line=start_line,
                    end_line=end_line,
                    parameters=params_info,
                    docstring=docstring,
                    body=function_body_content
                )
                functions.append(func_info)
                print(f"Code Analyzer: Found top-level function: '{function_name}' (Lines {start_line}-{end_line})")
                
            elif node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                class_body_node = node.child_by_field_name('body') # Get the class body node

                class_name = name_node.text.decode('utf8') if name_node else "Unnamed Class"

                # Extract docstring from the beginning of the class body
                docstring = None
                if class_body_node and class_body_node.child_count > 0:
                    first_child_of_body = class_body_node.child(0)
                    docstring = _extract_docstring(first_child_of_body, code_bytes)

                # Extract class body content
                class_body_content = _extract_body_content(class_body_node, code_bytes) if class_body_node else None

                class_info = ClassInfo(
                    name=class_name,
                    start_line=start_line,
                    end_line=end_line,
                    docstring=docstring,
                    body=class_body_content
                )
                classes.append(class_info)
                print(f"Code Analyzer: Found top-level class: '{class_name}' (Lines {start_line}-{end_line})")
                    
                # --- Nested traversal for class methods ---
                if class_body_node:
                    body_cursor = class_body_node.walk() 

                    if body_cursor.goto_first_child():
                        while True:
                            method_node = body_cursor.node
                            if method_node.type == 'function_definition':
                                method_name_node = method_node.child_by_field_name('name')
                                parameters_node = method_node.child_by_field_name('parameters')
                                method_body_node = method_node.child_by_field_name('body') # Get method body node

                                method_name = method_name_node.text.decode('utf8') if method_name_node else "Unnamed Method"
                                method_start_line = method_node.start_point[0] + 1
                                method_end_line = method_node.end_point[0] + 1
                                
                                # Extract parameters for method
                                method_params_info = _extract_parameters(parameters_node, code_bytes)

                                # Extract docstring for method
                                method_docstring = None
                                if method_body_node and method_body_node.child_count > 0:
                                    first_child_of_method_body = method_body_node.child(0)
                                    method_docstring = _extract_docstring(first_child_of_method_body, code_bytes)

                                # Extract method body content
                                method_body_content = _extract_body_content(method_body_node, code_bytes) if method_body_node else None

                                method_info = FunctionInfo(
                                    name=method_name,
                                    start_line=method_start_line,
                                    end_line=method_end_line,
                                    parameters=method_params_info,
                                    docstring=method_docstring,
                                    body=method_body_content
                                )
                                class_info.methods.append(method_info)
                                print(f"    Code Analyzer: Found method: '{method_name}' in '{class_name}' (Lines {method_start_line}-{method_end_line})")
                            
                            if not body_cursor.goto_next_sibling():
                                break
                    # --- End nested traversal ---

            # Move to the next top-level sibling
            if not cursor.goto_next_sibling():
                break

    print("\nCode Analyzer: Code analysis complete.")
    return {"functions": functions, "classes": classes} # Return extracted info

# --- Test execution (for initial setup confirmation) ---
if __name__ == "__main__":
    print("Starting Code Analyzer module test...")
    
    # Initialize the parser
    parser = initialize_python_parser()

    # Example Python code (slightly more complex for docstrings and params)
    python_code_example = """
# This is a sample module
def greet(name: str = "World", greeting: Optional[str] = None):
    \"\"\"
    Greets the given name with an optional greeting.
    
    Args:
        name (str): The name to greet.
        greeting (str, optional): The custom greeting. Defaults to "Hello".
    \"\"\"
    if greeting:
        print(f"{greeting}, {name}!")
    else:
        print(f"Hello, {name}!")

class Calculator:
    \"\"\"
    A simple calculator class for basic arithmetic.
    
    Attributes:
        value (int): The current value of the calculator.
    \"\"\"
    def __init__(self, initial_value: int = 0):
        \"\"\"
        Initializes the Calculator with a starting value.
        
        Args:
            initial_value (int): The initial numerical value.
        \"\"\"
        self.value = initial_value

    def add(self, a: int, b: int) -> int:
        \"\"\"
        Adds two numbers and returns the sum.
        
        Args:
            a (int): The first number.
            b (int): The second number.
            
        Returns:
            int: The sum of a and b.
        \"\"\"
        return a + b

def goodbye(name: str):
    \"\"\"Says goodbye to the given name.\"\"\"
    print(f"Goodbye, {name}!")
    """

    # Analyze the example code
    extracted_info = analyze_python_code(python_code_example, parser)
    
    print("\n--- Summary of Extracted Info (Detailed) ---")
    
    print(f"Total Functions Found: {len(extracted_info['functions'])}")
    for func in extracted_info['functions']:
        print(f"  - Function: {func.name} (Lines {func.start_line}-{func.end_line})")
        if func.docstring:
            print(f"    Docstring: {func.docstring[:50]}...") # Print first 50 chars of docstring
        if func.parameters:
            print("    Parameters:")
            for param in func.parameters:
                param_details = f"      - {param.name}"
                if param.type_annotation:
                    param_details += f": {param.type_annotation}"
                if param.default_value:
                    param_details += f" = {param.default_value}"
                print(param_details)
        if func.body:
            print(f"    Body (first 50 chars): '{func.body[:50]}...'")

    print(f"\nTotal Classes Found: {len(extracted_info['classes'])}")
    for cls in extracted_info['classes']:
        print(f"  - Class: {cls.name} (Lines {cls.start_line}-{cls.end_line})")
        if cls.docstring:
            print(f"    Docstring: {cls.docstring[:50]}...") # Print first 50 chars of docstring
        if cls.body:
            print(f"    Body (first 50 chars): '{cls.body[:50]}...'")
        
        if cls.methods:
            print("    Methods:")
            for method in cls.methods:
                print(f"      - Method: {method.name} (Lines {method.start_line}-{method.end_line})")
                if method.docstring:
                    print(f"        Docstring: {method.docstring[:50]}...")
                if method.parameters:
                    print("        Parameters:")
                    for param in method.parameters:
                        param_details = f"          - {param.name}"
                        if param.type_annotation:
                            param_details += f": {param.type_annotation}"
                        if param.default_value:
                            param_details += f" = {param.default_value}"
                        print(param_details)
                if method.body:
                    print(f"        Body (first 50 chars): '{method.body[:50]}...'")
    
    print("\nCode Analyzer module test complete.")