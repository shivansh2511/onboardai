# src/database/sqlite_manager.py
import sqlite3
import os
from typing import Optional, List
from datetime import datetime

# Import dataclasses from code_analyzer for type hinting
# We need to make sure these dataclasses are accessible,
# so we'll import them or define simple stubs if direct import creates circular dependency.
# For now, let's assume direct import is fine, or you'll define simple class structures if needed.
# However, the cleaner way is to keep dataclasses in a shared place or pass dicts.
# For simplicity, and avoiding premature over-engineering, let's assume we pass sufficient details.
# No, let's define them here too, or structure them in a 'models.py'
# The best approach is to define data models in a separate `src/models.py` file.
# For now, copying them to avoid circular imports. This will be refactored later.

# --- Data Structures for Code Elements (Copied for independent use) ---
# In a larger project, these would be in a shared `src/models.py`
# to avoid duplication and circular dependencies.
class ParameterInfo:
    def __init__(self, name: str, default_value: Optional[str] = None, type_annotation: Optional[str] = None):
        self.name = name
        self.default_value = default_value
        self.type_annotation = type_annotation

class VariableInfo:
    def __init__(self, name: str, value: Optional[str] = None, type_annotation: Optional[str] = None,
                 is_global: bool = False, is_class_attribute: bool = False,
                 is_function_local: bool = False, defined_at_line: int = -1, parent_scope: Optional[str] = None):
        self.name = name
        self.value = value
        self.type_annotation = type_annotation
        self.is_global = is_global
        self.is_class_attribute = is_class_attribute
        self.is_function_local = is_function_local
        self.defined_at_line = defined_at_line
        self.parent_scope = parent_scope

class FunctionInfo:
    def __init__(self, name: str, start_line: int, end_line: int, parameters: List[ParameterInfo],
                 docstring: Optional[str], body: Optional[str], variables: List[VariableInfo],
                 calls_made: List[str]):
        self.name = name
        self.start_line = start_line
        self.end_line = end_line
        self.parameters = parameters
        self.docstring = docstring
        self.body = body
        self.variables = variables
        self.calls_made = calls_made

class ClassInfo:
    def __init__(self, name: str, start_line: int, end_line: int, docstring: Optional[str],
                 methods: List[FunctionInfo], body: Optional[str], attributes: List[VariableInfo]):
        self.name = name
        self.start_line = start_line
        self.end_line = end_line
        self.docstring = docstring
        self.methods = methods
        self.body = body
        self.attributes = attributes


class SQLiteManager:
    def __init__(self, db_name='onboardai.db'):
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        
        self.data_dir = os.path.join(project_root, 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.data_dir, db_name)
        self.conn = None
        self.cursor = None
        print(f"Database Manager: Initialized for DB: {self.db_path}")

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            print("Database Manager: Connection established successfully.")
        except sqlite3.Error as e:
            print(f"Database Manager Error: Failed to connect to database: {e}")
            self.conn = None
            self.cursor = None

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
            print("Database Manager: Connection closed.")

    def _execute_query(self, query: str, params: tuple = ()) -> bool:
        if not self.conn:
            print("Database Manager Error: No database connection.")
            return False
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database Manager Error: SQL execution failed: {e}")
            return False

    def create_tables(self):
        if not self.conn:
            print("Database Manager Error: Cannot create tables, no connection.")
            return False

        print("Database Manager: Creating tables...")

        files_table_query = """
        CREATE TABLE IF NOT EXISTS Files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            last_modified_at DATETIME,
            checksum TEXT,
            full_content TEXT
        );
        """
        classes_table_query = """
        CREATE TABLE IF NOT EXISTS Classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_line INTEGER,
            end_line INTEGER,
            docstring TEXT,
            body TEXT,
            FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE
        );
        """
        functions_table_query = """
        CREATE TABLE IF NOT EXISTS Functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            class_id INTEGER NULL,
            name TEXT NOT NULL,
            start_line INTEGER,
            end_line INTEGER,
            docstring TEXT,
            body TEXT,
            signature TEXT,
            FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES Classes(id) ON DELETE CASCADE
        );
        """
        parameters_table_query = """
        CREATE TABLE IF NOT EXISTS Parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type_annotation TEXT,
            default_value TEXT,
            FOREIGN KEY (function_id) REFERENCES Functions(id) ON DELETE CASCADE
        );
        """
        variables_table_query = """
        CREATE TABLE IF NOT EXISTS Variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NULL,
            class_id INTEGER NULL,
            function_id INTEGER NULL,
            name TEXT NOT NULL,
            value TEXT,
            type_annotation TEXT,
            is_global BOOLEAN NOT NULL,
            is_class_attribute BOOLEAN NOT NULL,
            is_function_local BOOLEAN NOT NULL,
            defined_at_line INTEGER,
            FOREIGN KEY (file_id) REFERENCES Files(id) ON DELETE CASCADE,
            FOREIGN KEY (class_id) REFERENCES Classes(id) ON DELETE CASCADE,
            FOREIGN KEY (function_id) REFERENCES Functions(id) ON DELETE CASCADE
        );
        """
        function_calls_table_query = """
        CREATE TABLE IF NOT EXISTS FunctionCalls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calling_function_id INTEGER NOT NULL,
            called_name TEXT NOT NULL,
            call_line_number INTEGER,
            FOREIGN KEY (calling_function_id) REFERENCES Functions(id) ON DELETE CASCADE
        );
        """

        queries = [
            files_table_query,
            classes_table_query,
            functions_table_query,
            parameters_table_query,
            variables_table_query,
            function_calls_table_query
        ]

        success = True
        for query in queries:
            if not self._execute_query(query):
                success = False
                break
        
        if success:
            print("Database Manager: All tables created successfully (or already existed).")
        else:
            print("Database Manager Error: Failed to create one or more tables.")
        return success

    def insert_file(self, path: str, last_modified_at: str, checksum: str, full_content: str) -> Optional[int]:
        query = """
        INSERT INTO Files (path, last_modified_at, checksum, full_content)
        VALUES (?, ?, ?, ?)
        """
        if self._execute_query(query, (path, last_modified_at, checksum, full_content)):
            return self.cursor.lastrowid
        return None

    def get_file_by_path(self, path: str):
        query = "SELECT id, path, last_modified_at, checksum, full_content FROM Files WHERE path = ?"
        self.cursor.execute(query, (path,))
        return self.cursor.fetchone()

    # --- NEW INSERT METHODS FOR CODE STRUCTURES ---

    def insert_class(self, file_id: int, class_info: ClassInfo) -> Optional[int]:
        query = """
        INSERT INTO Classes (file_id, name, start_line, end_line, docstring, body)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (file_id, class_info.name, class_info.start_line, class_info.end_line,
                  class_info.docstring, class_info.body)
        if self._execute_query(query, params):
            return self.cursor.lastrowid
        return None

    def insert_function(self, file_id: int, class_id: Optional[int], func_info: FunctionInfo) -> Optional[int]:
        query = """
        INSERT INTO Functions (file_id, class_id, name, start_line, end_line, docstring, body, signature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        # A simple signature for now. You might want to generate a more robust one from parameters.
        signature = f"{func_info.name}({', '.join([p.name for p in func_info.parameters])})"
        
        params = (file_id, class_id, func_info.name, func_info.start_line, func_info.end_line,
                  func_info.docstring, func_info.body, signature)
        if self._execute_query(query, params):
            return self.cursor.lastrowid
        return None

    def insert_parameter(self, function_id: int, param_info: ParameterInfo) -> Optional[int]:
        query = """
        INSERT INTO Parameters (function_id, name, type_annotation, default_value)
        VALUES (?, ?, ?, ?)
        """
        params = (function_id, param_info.name, param_info.type_annotation, param_info.default_value)
        if self._execute_query(query, params):
            return self.cursor.lastrowid
        return None

    def insert_variable(self, variable_info: VariableInfo, file_id: Optional[int] = None, 
                        class_id: Optional[int] = None, function_id: Optional[int] = None) -> Optional[int]:
        query = """
        INSERT INTO Variables (file_id, class_id, function_id, name, value, type_annotation, 
                               is_global, is_class_attribute, is_function_local, defined_at_line)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (file_id, class_id, function_id, variable_info.name, variable_info.value,
                  variable_info.type_annotation, variable_info.is_global,
                  variable_info.is_class_attribute, variable_info.is_function_local,
                  variable_info.defined_at_line)
        if self._execute_query(query, params):
            return self.cursor.lastrowid
        return None

    def insert_function_call(self, calling_function_id: int, called_name: str, call_line_number: int) -> Optional[int]:
        query = """
        INSERT INTO FunctionCalls (calling_function_id, called_name, call_line_number)
        VALUES (?, ?, ?)
        """
        params = (calling_function_id, called_name, call_line_number)
        if self._execute_query(query, params):
            return self.cursor.lastrowid
        return None


# --- Test execution for SQLiteManager (for initial setup confirmation) ---
if __name__ == "__main__":
    print("Starting SQLiteManager module test...")
    db_manager = SQLiteManager()
    
    try:
        db_manager.connect()
        if db_manager.create_tables():
            print("\nTest: Tables created successfully. You can now check the 'data/onboardai.db' file.")
            
            # Example: Insert a dummy file
            test_file_path = "/path/to/test_file.py"
            test_modified_at = datetime.now().isoformat()
            test_checksum = "abc123def456"
            test_content = "print('hello world')"

            print(f"\nTest: Attempting to insert dummy file: {test_file_path}")
            file_id = db_manager.insert_file(test_file_path, test_modified_at, test_checksum, test_content)
            if file_id:
                print(f"Test: Dummy file inserted with ID: {file_id}")
                retrieved_file = db_manager.get_file_by_path(test_file_path)
                if retrieved_file:
                    print(f"Test: Retrieved file: {retrieved_file[1]} (ID: {retrieved_file[0]})")
                else:
                    print("Test: Failed to retrieve dummy file.")
                
                # Test inserting a dummy class and function related to this file
                dummy_class_info = ClassInfo(
                    name="MyTestClass", start_line=1, end_line=10, docstring="A test class.",
                    methods=[], body="class MyTestClass:\n    pass", attributes=[]
                )
                class_id = db_manager.insert_class(file_id, dummy_class_info)
                if class_id:
                    print(f"Test: Dummy class inserted with ID: {class_id}")
                
                dummy_func_info = FunctionInfo(
                    name="test_func", start_line=1, end_line=5, parameters=[],
                    docstring="A test function.", body="def test_func():\n    pass",
                    variables=[], calls_made=[]
                )
                function_id = db_manager.insert_function(file_id, None, dummy_func_info) # None for class_id (top-level)
                if function_id:
                    print(f"Test: Dummy function inserted with ID: {function_id}")

                    # Test inserting a parameter for the dummy function
                    dummy_param = ParameterInfo(name="arg1", type_annotation="str")
                    param_id = db_manager.insert_parameter(function_id, dummy_param)
                    if param_id:
                        print(f"Test: Dummy parameter inserted with ID: {param_id}")

                    # Test inserting a variable for the dummy function
                    dummy_var = VariableInfo(name="x", value="10", is_function_local=True, defined_at_line=2)
                    var_id = db_manager.insert_variable(dummy_var, function_id=function_id)
                    if var_id:
                        print(f"Test: Dummy variable inserted with ID: {var_id}")
                    
                    # Test inserting a function call
                    call_id = db_manager.insert_function_call(function_id, "print", 3)
                    if call_id:
                        print(f"Test: Dummy function call inserted with ID: {call_id}")
            else:
                print("Test: Failed to insert dummy file.")
        else:
            print("\nTest: Failed to create tables.")
    finally:
        db_manager.close()
    print("SQLiteManager module test complete.")