# src/code_analyzer.py
from tree_sitter import Language, Parser, Tree, Node
import os
import tree_sitter_python as tspython # For loading the Python grammar
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime # Added for timestamp for file entry

# Import SQLiteManager
from .database.sqlite_manager import SQLiteManager # <--- ADDED: Import SQLiteManager

# --- Data Structures for Code Elements (Keep as is - these are dataclasses) ---
# Note: In a larger project, these dataclasses would ideally be in a shared `src/models.py`
# file to avoid duplication and potential circular dependencies.
@dataclass
class ParameterInfo:
    """Represents information about a function parameter."""
    name: str
    default_value: Optional[str] = None # For parameters like `param=None`
    type_annotation: Optional[str] = None # For parameters like `param: int`

@dataclass
class VariableInfo:
    """Represents information about a variable definition/assignment."""
    name: str
    value: Optional[str] = None
    type_annotation: Optional[str] = None # For variables like `x: int = 10`
    is_global: bool = False # True if defined at module level
    is_class_attribute: bool = False # True if defined directly in a class body (not method)
    is_function_local: bool = False # True if defined inside a function/method
    defined_at_line: int = -1
    parent_scope: Optional[str] = None # Name of the function/class it's defined within

@dataclass
class FunctionInfo:
    """Represents information about a function."""
    name: str
    start_line: int
    end_line: int
    parameters: List[ParameterInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    body: Optional[str] = None # The code content of the function body
    variables: List[VariableInfo] = field(default_factory=list) # Added for local variables
    calls_made: List[str] = field(default_factory=list) # List to store names of called functions/methods

@dataclass
class ClassInfo:
    """Represents information about a class."""
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    methods: List[FunctionInfo] = field(default_factory=list)
    body: Optional[str] = None # The code content of the class body
    attributes: List[VariableInfo] = field(default_factory=list) # Added for class attributes


# --- Helper Functions for Extraction (Keep these as standalone functions) ---

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
        name_node = None
        for child in param_node.named_children:
            if child.type == 'identifier':
                name_node = child
                break
        type_node = param_node.child_by_field_name('type')

        if name_node:
            name = name_node.text.decode('utf8')
        if type_node:
            type_annotation = type_node.text.decode('utf8')

    elif param_node.type == 'default_parameter':
        name_field_node = param_node.child_by_field_name('name')
        value_node = param_node.child_by_field_name('value')

        if value_node:
            default_value = value_node.text.decode('utf8')

        if name_field_node:
            if name_field_node.type == 'typed_parameter':
                temp_param_info = _parse_single_parameter_node(name_field_node, code_string)
                if temp_param_info:
                    name = temp_param_info.name
                    type_annotation = temp_param_info.type_annotation
            elif name_field_node.type == 'identifier':
                name = name_field_node.text.decode('utf8')

    elif param_node.type == 'typed_default_parameter':
        name_node = None
        for child in param_node.named_children:
            if child.type == 'identifier':
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

    elif param_node.type == 'list_splat_pattern':
        name_node = param_node.child_by_field_name('name')
        if name_node:
            name = "*" + name_node.text.decode('utf8')
    elif param_node.type == 'dictionary_splat_pattern':
        name_node = param_node.child_by_field_name('name')
        if name_node:
            name = "**" + name_node.text.decode('utf8')

    if name:
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

def _extract_variables_from_block(block_node: Node, code_string: bytes, scope_type: str, scope_name: Optional[str] = None) -> List[VariableInfo]:
    """
    Extracts variable assignments from a given block node.
    `scope_type` can be 'module', 'class', or 'function'.
    `scope_name` is the name of the class or function, if applicable.
    This function performs a shallow scan of the immediate children of the block for assignments.
    """
    variables: List[VariableInfo] = []
    
    if not block_node or block_node.type not in ['block', 'module']:
        return variables

    cursor = block_node.walk()
    if cursor.goto_first_child():
        while True:
            statement_node = cursor.node
            
            if statement_node.type == 'expression_statement':
                expr_node = statement_node.child(0)
                if expr_node:
                    if expr_node.type == 'assignment':
                        left_side = expr_node.child_by_field_name('left')
                        right_side = expr_node.child_by_field_name('right')
                        
                        if left_side and (left_side.type == 'identifier' or left_side.type == 'attribute'):
                            var_name = left_side.text.decode('utf8')
                            var_value = right_side.text.decode('utf8') if right_side else None
                            
                            is_class_attr = (scope_type == 'class' and left_side.type == 'identifier')


                            variables.append(VariableInfo(
                                name=var_name,
                                value=var_value,
                                is_global=(scope_type == 'module'),
                                is_class_attribute=is_class_attr,
                                is_function_local=(scope_type == 'function'),
                                defined_at_line=statement_node.start_point[0] + 1,
                                parent_scope=scope_name
                            ))
                    elif expr_node.type == 'typed_assignment':
                        left_side = expr_node.child_by_field_name('left')
                        type_node = expr_node.child_by_field_name('type')
                        right_side = expr_node.child_by_field_name('right')

                        if left_side and left_side.type == 'identifier':
                            var_name = left_side.text.decode('utf8')
                            var_type = type_node.text.decode('utf8') if type_node else None
                            var_value = right_side.text.decode('utf8') if right_side else None

                            variables.append(VariableInfo(
                                name=var_name,
                                value=var_value,
                                type_annotation=var_type,
                                is_global=(scope_type == 'module'),
                                is_class_attribute=(scope_type == 'class'),
                                is_function_local=(scope_type == 'function'),
                                defined_at_line=statement_node.start_point[0] + 1,
                                parent_scope=scope_name
                            ))
            elif statement_node.type == 'decorated_definition':
                definition_node = statement_node.child_by_field_name('definition')
                if definition_node and definition_node.type == 'class_definition':
                    pass
                elif definition_node and definition_node.type == 'function_definition':
                    pass

            if not cursor.goto_next_sibling():
                break
    return variables


def _extract_calls_from_block(block_node: Node, code_string: bytes) -> List[str]:
    """
    Extracts names of functions/methods called from within a given block node.
    This performs a shallow scan for call expressions and recursively searches in nested blocks.
    """
    called_names: List[str] = []
    if not block_node or block_node.type not in ['block', 'module']:
        return called_names

    cursor = block_node.walk()
    if cursor.goto_first_child():
        while True:
            node = cursor.node
            
            if node.type == 'call':
                function_or_method_node = node.child(0) 
                if function_or_method_node:
                    if function_or_method_node.type == 'identifier':
                        called_names.append(function_or_method_node.text.decode('utf8'))
                    elif function_or_method_node.type == 'attribute':
                        method_name_node = function_or_method_node.child_by_field_name('attribute')
                        if method_name_node and method_name_node.type == 'identifier':
                            called_names.append(method_name_node.text.decode('utf8'))

            if node.type in ['block', 'if_statement', 'for_statement', 'while_statement', 'with_statement', 'try_statement', 'except_clause', 'finally_clause']:
                called_names.extend(_extract_calls_from_block(node, code_string))

            if not cursor.goto_next_sibling():
                break
    return called_names

def _print_ast_node(node: Node, indent: str = "", include_fields: bool = False):
    """
    Recursively prints the AST nodes, showing their type and text.
    Optionally includes field names for better understanding of node relationships.
    """
    node_text = node.text.decode('utf8').strip().split('\n')[0]
    print(f"{indent}Type: {node.type}, Text: '{node_text}'")

    if include_fields:
        for field_name, child_node in node.children_by_field_name():
            if child_node:
                child_text = child_node.text.decode('utf8').strip().split('\n')[0]
                print(f"{indent}  Field: {field_name}, Type: {child_node.type}, Text: '{child_text}'")

    for child in node.children:
        _print_ast_node(child, indent + "  ", include_fields)


# --- Main CodeAnalyzer Class (New Structure for src/code_analyzer.py) ---

class CodeAnalyzer:
    def __init__(self, language_name: str = "python", db_manager: Optional[SQLiteManager] = None): # <--- MODIFIED: Added db_manager
        self.language_name = language_name.lower()
        self.parser: Optional[Parser] = None
        self.db_manager = db_manager # <--- STORED: db_manager
        self._initialize_language_parser()

    def _initialize_language_parser(self):
        """Initializes the Tree-sitter parser for the specified language."""
        try:
            if self.language_name == "python":
                language = Language(tspython.language())
            else:
                raise ValueError(f"Unsupported language: {self.language_name}")

            self.parser = Parser(language)
            print(f"Code Analyzer: {self.language_name.capitalize()} Tree-sitter parser initialized.")
        except Exception as e:
            print(f"Code Analyzer Error: Failed to initialize {self.language_name.capitalize()} parser: {e}")
            print(f"Please ensure `tree-sitter-{self.language_name}` is installed and compatible.")
            self.parser = None

    def analyze_code(self, code_string: str, file_path: str = "temp_code.py") -> dict: # <--- MODIFIED: Added file_path
        """
        Parses code string for the initialized language and extracts structured information.
        Optionally persists this information to the database if a db_manager is provided.
        Returns a dictionary with extracted data including functions, classes, and top-level variables.
        """
        if not self.parser:
            print("Parser not initialized. Cannot analyze code.")
            return {}

        print("\nCode Analyzer: Parsing code...")
        code_bytes = code_string.encode("utf8")
        tree = self.parser.parse(code_bytes)
        
        print("Code Analyzer: AST Root Node Type:", tree.root_node.type)
        print("Code Analyzer: AST Root Node Text (first 100 chars):", tree.root_node.text.decode('utf8')[:100] + "...")

        functions: List[FunctionInfo] = []
        classes: List[ClassInfo] = []

        file_id = None
        if self.db_manager:
            print(f"Code Analyzer: Persisting file info for {file_path}...")
            # Generate a simple checksum (e.g., hash of content) for change detection
            import hashlib
            checksum = hashlib.md5(code_bytes).hexdigest()
            # Check if file already exists in DB
            existing_file = self.db_manager.get_file_by_path(file_path)
            if existing_file:
                # If content or modification time changed, update it. For this MVP, we re-insert or skip.
                # Simplification: For now, if it exists, use its ID. In a real system, you'd update if checksum differs.
                file_id = existing_file[0]
                print(f"Code Analyzer: File '{file_path}' already in DB with ID {file_id}. Skipping re-insertion.")
                # You might want to delete existing associated entities here to re-analyze from scratch
                # e.g., self.db_manager.delete_entities_for_file(file_id) (Requires new methods in SQLiteManager)
            else:
                file_id = self.db_manager.insert_file(file_path, datetime.now().isoformat(), checksum, code_string)
                if file_id:
                    print(f"Code Analyzer: File '{file_path}' inserted into DB with ID: {file_id}")
                else:
                    print(f"Code Analyzer Error: Failed to insert file '{file_path}' into DB.")


        cursor = tree.walk()

        if cursor.goto_first_child():
            while True:
                node = cursor.node
                
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                if node.type == 'function_definition':
                    name_node = node.child_by_field_name('name')
                    parameters_node = node.child_by_field_name('parameters')
                    body_node = node.child_by_field_name('body')

                    function_name = name_node.text.decode('utf8') if name_node else "Unnamed Function"
                    
                    params_info = _extract_parameters(parameters_node, code_bytes)

                    docstring = None
                    if body_node and body_node.child_count > 0:
                        first_child_of_body = body_node.child(0)
                        docstring = _extract_docstring(first_child_of_body, code_bytes)
                    
                    function_body_content = _extract_body_content(body_node, code_bytes) if body_node else None

                    func_local_variables = _extract_variables_from_block(body_node, code_bytes, 'function', function_name)

                    func_calls_made = _extract_calls_from_block(body_node, code_bytes)

                    func_info = FunctionInfo(
                        name=function_name,
                        start_line=start_line,
                        end_line=end_line,
                        parameters=params_info,
                        docstring=docstring,
                        body=function_body_content,
                        variables=func_local_variables,
                        calls_made=func_calls_made
                    )
                    functions.append(func_info)
                    print(f"Code Analyzer: Found top-level function: '{function_name}' (Lines {start_line}-{end_line})")
                    
                    # --- NEW: Persist Function and its children ---
                    if self.db_manager and file_id:
                        function_db_id = self.db_manager.insert_function(file_id, None, func_info) # None for class_id (top-level)
                        if function_db_id:
                            for param in params_info:
                                self.db_manager.insert_parameter(function_db_id, param)
                            for var in func_local_variables:
                                self.db_manager.insert_variable(var, function_id=function_db_id)
                            for called_name in func_calls_made:
                                # For simplicity, line number of call isn't captured yet, defaulting to func start line
                                self.db_manager.insert_function_call(function_db_id, called_name, func_info.start_line)


                elif node.type == 'class_definition':
                    name_node = node.child_by_field_name('name')
                    class_body_node = node.child_by_field_name('body')

                    class_name = name_node.text.decode('utf8') if name_node else "Unnamed Class"

                    docstring = None
                    if class_body_node and class_body_node.child_count > 0:
                        first_child_of_body = class_body_node.child(0)
                        docstring = _extract_docstring(first_child_of_body, code_bytes)

                    class_body_content = _extract_body_content(class_body_node, code_bytes) if class_body_node else None

                    class_attributes = _extract_variables_from_block(class_body_node, code_bytes, 'class', class_name)


                    class_info = ClassInfo(
                        name=class_name,
                        start_line=start_line,
                        end_line=end_line,
                        docstring=docstring,
                        body=class_body_content,
                        attributes=class_attributes
                    )
                    classes.append(class_info)
                    print(f"Code Analyzer: Found top-level class: '{class_name}' (Lines {start_line}-{end_line})")
                        
                    # --- NEW: Persist Class and its attributes ---
                    class_db_id = None
                    if self.db_manager and file_id:
                        class_db_id = self.db_manager.insert_class(file_id, class_info)
                        if class_db_id:
                            for attr in class_attributes:
                                self.db_manager.insert_variable(attr, class_id=class_db_id)

                    if class_body_node:
                        body_cursor = class_body_node.walk() 

                        if body_cursor.goto_first_child():
                            while True:
                                method_node = body_cursor.node
                                if method_node.type == 'function_definition':
                                    method_name_node = method_node.child_by_field_name('name')
                                    parameters_node = method_node.child_by_field_name('parameters')
                                    method_body_node = method_node.child_by_field_name('body')

                                    method_name = method_name_node.text.decode('utf8') if method_name_node else "Unnamed Method"
                                    method_start_line = method_node.start_point[0] + 1
                                    method_end_line = method_node.end_point[0] + 1
                                    
                                    method_params_info = _extract_parameters(parameters_node, code_bytes)

                                    method_docstring = None
                                    if method_body_node and method_body_node.child_count > 0:
                                        first_child_of_method_body = method_body_node.child(0)
                                        method_docstring = _extract_docstring(first_child_of_method_body, code_bytes)

                                    method_body_content = _extract_body_content(method_body_node, code_bytes) if method_body_node else None

                                    method_local_variables = _extract_variables_from_block(method_body_node, code_bytes, 'function', method_name)

                                    method_calls_made = _extract_calls_from_block(method_body_node, code_bytes)

                                    method_info = FunctionInfo(
                                        name=method_name,
                                        start_line=method_start_line,
                                        end_line=method_end_line,
                                        parameters=method_params_info,
                                        docstring=method_docstring,
                                        body=method_body_content,
                                        variables=method_local_variables,
                                        calls_made=method_calls_made
                                    )
                                    class_info.methods.append(method_info)
                                    print(f"    Code Analyzer: Found method: '{method_name}' in '{class_name}' (Lines {method_start_line}-{method_end_line})")
                                    
                                    # --- NEW: Persist Method and its children ---
                                    if self.db_manager and file_id and class_db_id:
                                        method_db_id = self.db_manager.insert_function(file_id, class_db_id, method_info)
                                        if method_db_id:
                                            for param in method_params_info:
                                                self.db_manager.insert_parameter(method_db_id, param)
                                            for var in method_local_variables:
                                                self.db_manager.insert_variable(var, function_id=method_db_id)
                                            for called_name in method_calls_made:
                                                self.db_manager.insert_function_call(method_db_id, called_name, method_info.start_line)
                                
                                if not body_cursor.goto_next_sibling():
                                    break

                if not cursor.goto_next_sibling():
                    break

        top_level_variables = _extract_variables_from_block(tree.root_node, code_bytes, 'module')

        # --- NEW: Persist Top-Level Variables ---
        if self.db_manager and file_id:
            for var in top_level_variables:
                self.db_manager.insert_variable(var, file_id=file_id)


        print("\nCode Analyzer: Code analysis complete.")
        return {"functions": functions, "classes": classes, "top_level_variables": top_level_variables}


# --- Test execution (for initial setup confirmation - REVISED for Class) ---
if __name__ == "__main__":
    print("Starting Code Analyzer module test (via Class instance)...")
    
    # Initialize DB Manager for testing
    db_manager_test = SQLiteManager()
    db_manager_test.connect()
    db_manager_test.create_tables() # Ensure tables exist

    analyzer = CodeAnalyzer(language_name="python", db_manager=db_manager_test) # <--- MODIFIED: Pass db_manager

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

    test_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_code.py')) # A more robust test path

    extracted_info = analyzer.analyze_code(python_code_example, file_path=test_file_path) # <--- MODIFIED: Pass file_path
    
    print("\n--- Full AST Visualization ---")
    _print_ast_node(analyzer.parser.parse(python_code_example.encode("utf8")).root_node)


    print("\n--- Summary of Extracted Info (Detailed) ---")
    
    print("\n--- Top-Level Variables ---")
    if extracted_info['top_level_variables']:
        for var in extracted_info['top_level_variables']:
            details = f"  - {var.name}"
            if var.type_annotation:
                details += f": {var.type_annotation}"
            if var.value:
                details += f" = {var.value}"
            details += f" (Line: {var.defined_at_line})"
            print(details)
    else:
        print("  No top-level variables found.")


    print(f"\nTotal Functions Found: {len(extracted_info['functions'])}")
    for func in extracted_info['functions']:
        print(f"  - Function: {func.name} (Lines {func.start_line}-{func.end_line})")
        if func.docstring:
            print(f"    Docstring: {func.docstring[:50]}...")
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
        if func.variables:
            print("    Local Variables:")
            for var in func.variables:
                details = f"          - {var.name}"
                if var.type_annotation:
                    details += f": {var.type_annotation}"
                if var.value:
                    details += f" = {var.value}"
                details += f" (Line: {var.defined_at_line})"
                print(details)
        if func.calls_made:
            print("    Calls Made:")
            for call_name in func.calls_made:
                print(f"      - {call_name}")


    print(f"\nTotal Classes Found: {len(extracted_info['classes'])}")
    for cls in extracted_info['classes']:
        print(f"  - Class: {cls.name} (Lines {cls.start_line}-{cls.end_line})")
        if cls.docstring:
            print(f"    Docstring: {cls.docstring[:50]}...")
        if cls.body:
            print(f"    Body (first 50 chars): '{cls.body[:50]}...'")
        
        if cls.attributes:
            print("    Class Attributes:")
            for attr in cls.attributes:
                details = f"      - {attr.name}"
                if attr.type_annotation:
                    details += f": {attr.type_annotation}"
                if attr.value:
                    details += f" = {attr.value}"
                details += f" (Line: {attr.defined_at_line})"
                print(details)
        
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
                if method.variables:
                    print("        Local Variables:")
                    for var in method.variables:
                        details = f"          - {var.name}"
                        if var.type_annotation:
                            details += f": {var.type_annotation}"
                        if var.value:
                            details += f" = {var.value}"
                        details += f" (Line: {var.defined_at_line})"
                        print(details)
                if method.calls_made:
                    print("        Calls Made:")
                    for call_name in method.calls_made:
                        print(f"          - {call_name}")
    
    print("\nCode Analyzer module test complete.")
    db_manager_test.close() # <--- MODIFIED: Close DB connection after test