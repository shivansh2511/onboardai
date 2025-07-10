# src/code_analyzer.py
from tree_sitter import Language, Parser, Node
import os
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import hashlib
import datetime

@dataclass
class ParameterInfo:
    """Represents information about a function parameter."""
    name: str
    default_value: Optional[str] = None
    type_annotation: Optional[str] = None

@dataclass
class VariableInfo:
    """Represents information about a variable definition/assignment."""
    name: str
    value: Optional[str] = None
    type_annotation: Optional[str] = None
    is_global: bool = False
    is_class_attribute: bool = False
    is_function_local: bool = False
    defined_at_line: int = -1
    parent_scope: Optional[str] = None

@dataclass
class FunctionInfo:
    """Represents information about a function."""
    name: str
    start_line: int
    end_line: int
    parameters: List[ParameterInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    body: Optional[str] = None
    variables: List[VariableInfo] = field(default_factory=list)
    calls_made: List[str] = field(default_factory=list)

@dataclass
class ClassInfo:
    """Represents information about a class."""
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    methods: List[FunctionInfo] = field(default_factory=list)
    body: Optional[str] = None
    attributes: List[VariableInfo] = field(default_factory=list)

@dataclass
class AnalysisResults:
    """Aggregated results of the code analysis."""
    file_path: str
    module_docstring: Optional[str] = None
    top_level_variables: List[VariableInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)

class CodeAnalyzer:
    def __init__(self, language_name: str, db_manager, file_extension: str = None):
        self.db_manager = db_manager
        self.language = language_name.lower()
        self.file_extension = file_extension.lower() if file_extension else None
        try:
            if self.language == "python":
                self.parser = Parser(Language(tspython.language()))
                print("Code Analyzer: Python Tree-sitter parser initialized.")
            elif self.language == "javascript":
                if self.file_extension == "ts":
                    try:
                        self.parser = Parser(Language(tstypescript.typescript()))
                        print("Code Analyzer: TypeScript Tree-sitter parser initialized.")
                    except AttributeError:
                        try:
                            self.parser = Parser(Language(tstypescript.language_typescript()))
                            print("Code Analyzer: TypeScript Tree-sitter parser initialized (using language_typescript).")
                        except AttributeError as e:
                            print(f"Error: Failed to initialize TypeScript parser: {e}")
                            print("Please ensure `tree-sitter-typescript` is installed correctly and has `typescript` or `language_typescript` attribute.")
                            exit(1)
                else:
                    self.parser = Parser(Language(tsjavascript.language()))
                    print("Code Analyzer: JavaScript Tree-sitter parser initialized.")
            else:
                raise ValueError(f"Unsupported language: {language_name}")
        except Exception as e:
            print(f"Error initializing parser for {language_name}: {e}")
            print(f"Please ensure `tree-sitter-{language_name.lower()}`{' or tree-sitter-typescript' if self.file_extension == 'ts' else ''} is installed and compatible.")
            exit(1)

    def _get_node_text(self, node: Node, source_code_bytes: bytes) -> str:
        """Helper to get the text of a node."""
        return source_code_bytes[node.start_byte:node.end_byte].decode('utf8')

    def _extract_parameters(self, func_node: Node, source_code_bytes: bytes) -> List[ParameterInfo]:
        parameters = []
        parameters_node = func_node.child_by_field_name('parameters')
        print(f"Extracting parameters for node: {self._get_node_text(func_node, source_code_bytes)[:50]}...")
        if parameters_node:
            print(f"Parameters node found: {self._get_node_text(parameters_node, source_code_bytes)}")
            for child in parameters_node.named_children:
                print(f"Processing parameter node type: {child.type}, text: {self._get_node_text(child, source_code_bytes)}")
                if child.type == 'identifier':
                    param_name = self._get_node_text(child, source_code_bytes)
                    print(f"Found identifier parameter: {param_name}")
                    parameters.append(ParameterInfo(name=param_name))
                elif child.type == 'default_parameter' and self.language == 'python':
                    name_node = child.child_by_field_name('name')
                    value_node = child.child_by_field_name('value')
                    if name_node:
                        param_name = self._get_node_text(name_node, source_code_bytes)
                        param_value = self._get_node_text(value_node, source_code_bytes) if value_node else None
                        print(f"Found default parameter: {param_name} = {param_value}")
                        parameters.append(ParameterInfo(name=param_name, default_value=param_value))
                elif child.type in ['typed_parameter', 'typed_default_parameter'] and self.language == 'python':
                    param_name = None
                    param_type = None
                    param_value = None
                    print(f"Inspecting typed_parameter children: {[c.type for c in child.children]}")
                    for sub_child in child.children:
                        if sub_child.type == 'identifier':
                            param_name = self._get_node_text(sub_child, source_code_bytes)
                        elif sub_child.type == 'type':
                            param_type = self._get_node_text(sub_child, source_code_bytes)
                        elif sub_child.type == 'default':
                            param_value = self._get_node_text(sub_child, source_code_bytes)
                    if param_name:
                        print(f"Found typed parameter: {param_name}: {param_type} = {param_value}")
                        parameters.append(ParameterInfo(name=param_name, type_annotation=param_type, default_value=param_value))
                    else:
                        print(f"Skipping typed_parameter, no name found")
                elif child.type == 'parameter' and self.language == 'javascript':
                    param_name = None
                    param_type = None
                    param_value = None
                    print(f"Inspecting JS parameter children: {[c.type for c in child.named_children]}")
                    for sub_child in child.named_children:
                        if sub_child.type == 'identifier':
                            param_name = self._get_node_text(sub_child, source_code_bytes)
                        elif sub_child.type == 'type_annotation':
                            type_node = sub_child.named_child(0)
                            param_type = self._get_node_text(type_node, source_code_bytes) if type_node else None
                    if param_name:
                        print(f"Found JS parameter: {param_name}: {param_type} = {param_value}")
                        parameters.append(ParameterInfo(name=param_name, type_annotation=param_type, default_value=param_value))
                    else:
                        print(f"Skipping JS parameter, no name found")
                elif child.type == 'required_parameter' and self.language == 'javascript' and self.file_extension == 'ts':
                    param_name = None
                    param_type = None
                    param_value = None
                    print(f"Inspecting TS required_parameter children: {[c.type for c in child.named_children]}")
                    for sub_child in child.named_children:
                        if sub_child.type == 'identifier':
                            param_name = self._get_node_text(sub_child, source_code_bytes)
                        elif sub_child.type == 'type_annotation':
                            type_node = sub_child.named_child(0)
                            param_type = self._get_node_text(type_node, source_code_bytes) if type_node else None
                        elif sub_child.type in ['number', 'string', 'identifier']:  # Handle default value
                            param_value = self._get_node_text(sub_child, source_code_bytes)
                    if param_name:
                        print(f"Found TS required parameter: {param_name}: {param_type} = {param_value}")
                        parameters.append(ParameterInfo(name=param_name, type_annotation=param_type, default_value=param_value))
                    else:
                        print(f"Skipping TS required_parameter, no name found")
                elif child.type == 'optional_parameter' and self.language == 'javascript' and self.file_extension == 'ts':
                    param_name = None
                    param_type = None
                    param_value = None
                    print(f"Inspecting TS optional_parameter children: {[c.type for c in child.named_children]}")
                    for sub_child in child.named_children:
                        if sub_child.type == 'identifier':
                            param_name = self._get_node_text(sub_child, source_code_bytes)
                        elif sub_child.type == 'type_annotation':
                            type_node = sub_child.named_child(0)
                            param_type = self._get_node_text(type_node, source_code_bytes) if type_node else None
                        elif sub_child.type == 'assignment_expression':
                            value_node = sub_child.child_by_field_name('right')
                            param_value = self._get_node_text(value_node, source_code_bytes) if value_node else None
                    if param_name:
                        print(f"Found TS optional parameter: {param_name}: {param_type} = {param_value}")
                        parameters.append(ParameterInfo(name=param_name, type_annotation=param_type, default_value=param_value))
                    else:
                        print(f"Skipping TS optional_parameter, no name found")
                elif child.type in ['positional_wildcard_parameter', 'keyword_wildcard_parameter'] and self.language == 'python':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        param_name = self._get_node_text(name_node, source_code_bytes)
                        print(f"Found wildcard parameter: {param_name}")
                        parameters.append(ParameterInfo(name=param_name))
                else:
                    print(f"Skipping parameter node type: {child.type}")
        else:
            print("No parameters node found.")
        print(f"Extracted parameters: {[p.name for p in parameters]}")
        return parameters

    def _extract_variables(self, scope_node: Node, source_code_bytes: bytes,
                          is_global: bool = False, is_class_attribute: bool = False,
                          is_function_local: bool = False) -> List[VariableInfo]:
        variables = []
        seen_variables = set()
        print(f"Extracting variables with is_global={is_global}, is_class_attribute={is_class_attribute}, is_function_local={is_function_local}")
        print(f"Scope node type: {scope_node.type}")

        cursor = scope_node.walk()
        if cursor.goto_first_child():
            while True:
                node = cursor.node
                print(f"Processing node type: {node.type}, text: {self._get_node_text(node, source_code_bytes)[:100]}...")
                if node.type == 'ERROR':
                    print(f"Skipping ERROR node: {self._get_node_text(node, source_code_bytes)}")
                    if not cursor.goto_next_sibling():
                        break
                    continue
                if self.language == 'python' and node.type == 'expression_statement':
                    expression_node = node.named_child(0)
                    if expression_node:
                        print(f"Expression statement children: {[c.type for c in expression_node.named_children]}")
                        print(f"Expression statement all children: {[c.type for c in expression_node.children]}")
                        if expression_node.type == 'assignment':
                            name_node = expression_node.named_child(0)
                            if name_node and name_node.type == 'identifier':
                                var_name = self._get_node_text(name_node, source_code_bytes)
                                if var_name not in seen_variables:
                                    var_type = None
                                    var_value = None
                                    if len(expression_node.named_children) >= 3 and expression_node.named_child(1).type == 'type':
                                        var_type = self._get_node_text(expression_node.named_child(1), source_code_bytes)
                                        for i, child in enumerate(expression_node.children):
                                            if child.type == '=':
                                                value_node = expression_node.children[i + 1] if i + 1 < len(expression_node.children) else None
                                                var_value = self._get_node_text(value_node, source_code_bytes) if value_node else None
                                                print(f"Value node index: {i + 1}, type: {value_node.type if value_node else 'None'}, value: {var_value}")
                                                break
                                        print(f"Found annotated assignment: {var_name}: {var_type} = {var_value}")
                                    else:
                                        right_side = expression_node.named_child(1) if len(expression_node.named_children) > 1 else None
                                        var_value = self._get_node_text(right_side, source_code_bytes) if right_side else None
                                        print(f"Found assignment: {var_name} = {var_value}")
                                    variables.append(VariableInfo(
                                        name=var_name,
                                        value=var_value,
                                        type_annotation=var_type,
                                        is_global=is_global,
                                        is_class_attribute=is_class_attribute,
                                        is_function_local=is_function_local,
                                        defined_at_line=name_node.start_point[0] + 1
                                    ))
                                    seen_variables.add(var_name)
                        else:
                            print(f"Skipping expression_statement with child type: {expression_node.type}")
                elif self.language == 'javascript' and node.type in ['variable_declaration', 'lexical_declaration']:
                    print(f"JS declaration node text: {self._get_node_text(node, source_code_bytes)}")
                    print(f"JS declaration children: {[c.type for c in node.children]}")
                    for declarator in node.named_children:
                        if declarator.type == 'variable_declarator':
                            name_node = declarator.child_by_field_name('name')
                            value_node = declarator.child_by_field_name('value')
                            type_node = None
                            for child in declarator.children:
                                if child.type == 'type_annotation':
                                    type_node = child.named_child(0)
                                    break
                            if name_node:
                                var_name = self._get_node_text(name_node, source_code_bytes)
                                if var_name not in seen_variables:
                                    var_type = self._get_node_text(type_node, source_code_bytes) if type_node else None
                                    var_value = self._get_node_text(value_node, source_code_bytes) if value_node else None
                                    print(f"Found variable declaration: {var_name}: {var_type} = {var_value}")
                                    if value_node and value_node.type != 'arrow_function':
                                        variables.append(VariableInfo(
                                            name=var_name,
                                            value=var_value,
                                            type_annotation=var_type,
                                            is_global=is_global,
                                            is_class_attribute=is_class_attribute,
                                            is_function_local=is_function_local,
                                            defined_at_line=name_node.start_point[0] + 1
                                        ))
                                        seen_variables.add(var_name)
                elif self.language == 'javascript' and node.type == 'public_field_definition' and is_class_attribute:
                    name_node = node.child_by_field_name('name')
                    value_node = node.child_by_field_name('value')
                    type_node = None
                    for child in node.children:
                        if child.type == 'type_annotation':
                            type_node = child.named_child(0)
                            break
                    if name_node:
                        var_name = self._get_node_text(name_node, source_code_bytes)
                        if var_name not in seen_variables:
                            var_type = self._get_node_text(type_node, source_code_bytes) if type_node else None
                            var_value = self._get_node_text(value_node, source_code_bytes) if value_node else None
                            print(f"Found class attribute: {var_name}: {var_type} = {var_value}")
                            variables.append(VariableInfo(
                                name=var_name,
                                value=var_value,
                                type_annotation=var_type,
                                is_global=is_global,
                                is_class_attribute=is_class_attribute,
                                is_function_local=is_function_local,
                                defined_at_line=name_node.start_point[0] + 1
                            ))
                            seen_variables.add(var_name)
                if self.language == 'python' and node.type not in ['assignment', 'annotated_assignment'] and \
                   (not is_global or node.type not in ['function_definition', 'class_definition']):
                    variables.extend(self._extract_variables(node, source_code_bytes, is_global, is_class_attribute, is_function_local))
                elif self.language == 'javascript' and node.type not in ['variable_declaration', 'lexical_declaration', 'function_declaration', 'class_declaration', 'method_definition', 'public_field_definition', 'arrow_function']:
                    variables.extend(self._extract_variables(node, source_code_bytes, is_global, is_class_attribute, is_function_local))
                if not cursor.goto_next_sibling():
                    break
        print(f"Extracted variables: {[v.name for v in variables]}")
        return variables

    def _extract_function_calls(self, node: Node, source_code_bytes: bytes) -> List[str]:
        calls = []
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                current_node = cursor.node
                if current_node.type == 'ERROR':
                    print(f"Skipping ERROR node in function calls: {self._get_node_text(current_node, source_code_bytes)}")
                    if not cursor.goto_next_sibling():
                        break
                    continue
                if current_node.type == 'call' or (self.language == 'javascript' and current_node.type == 'call_expression'):
                    function_node = current_node.child_by_field_name('function')
                    if function_node:
                        if function_node.type == 'identifier':
                            calls.append(self._get_node_text(function_node, source_code_bytes))
                        elif function_node.type == 'member_expression' and self.language == 'javascript':
                            attribute_name_node = function_node.child_by_field_name('property')
                            if attribute_name_node:
                                calls.append(self._get_node_text(attribute_name_node, source_code_bytes))
                        elif function_node.type == 'attribute' and self.language == 'python':
                            attribute_name_node = function_node.child_by_field_name('attribute')
                            if attribute_name_node:
                                calls.append(self._get_node_text(attribute_name_node, source_code_bytes))
                if self.language == 'python' and current_node.type not in ['function_definition', 'class_definition', 'lambda']:
                    calls.extend(self._extract_function_calls(current_node, source_code_bytes))
                elif self.language == 'javascript' and current_node.type not in ['function_declaration', 'class_declaration', 'arrow_function', 'method_definition']:
                    calls.extend(self._extract_function_calls(current_node, source_code_bytes))
                if not cursor.goto_next_sibling():
                    break
        return list(set(calls))

    def _visit_function_definition(self, node: Node, source_code_bytes: bytes, file_id: int, class_id: Optional[int] = None, is_arrow: bool = False) -> Optional[FunctionInfo]:
        if is_arrow:
            # For arrow functions, node is variable_declarator; get arrow_function
            arrow_node = node.child_by_field_name('value')
            if not arrow_node or arrow_node.type != 'arrow_function':
                print(f"Error: Expected arrow_function node, got {arrow_node.type if arrow_node else 'None'}")
                return None
            name_node = node.child_by_field_name('name')
            parameters_node = arrow_node.child_by_field_name('parameters')
            body_node = arrow_node.child_by_field_name('body')
        else:
            name_node = node.child_by_field_name('name')
            parameters_node = node.child_by_field_name('parameters')
            body_node = node.child_by_field_name('body')
            arrow_node = node  # For non-arrow functions, use the original node

        if not name_node and not is_arrow:
            return None
        func_name = self._get_node_text(name_node, source_code_bytes) if name_node else "anonymous"
        start_line = node.start_point[0] + 1
        end_line = body_node.end_point[0] + 1 if body_node else node.end_point[0] + 1
        parameters = self._extract_parameters(arrow_node, source_code_bytes)
        print(f"Parameters for function '{func_name}': {[p.name for p in parameters]}")
        docstring = None
        if self.language == 'python' and body_node and body_node.children:
            first_child = body_node.children[0]
            if first_child.type == 'expression_statement' and first_child.children and \
               first_child.children[0].type == 'string':
                docstring = self._get_node_text(first_child.children[0], source_code_bytes).strip('\"\'')
        func_body_content = self._get_node_text(body_node, source_code_bytes) if body_node else None
        local_variables = []
        if body_node:
            local_variables = self._extract_variables(body_node, source_code_bytes, is_function_local=True)
            param_names = {p.name for p in parameters}
            local_variables = [v for v in local_variables if v.name not in param_names]
        calls_made = []
        if body_node:
            calls_made = self._extract_function_calls(body_node, source_code_bytes)
        func_info = FunctionInfo(
            name=func_name,
            start_line=start_line,
            end_line=end_line,
            parameters=parameters,
            docstring=docstring,
            body=func_body_content,
            variables=local_variables,
            calls_made=calls_made
        )
        db_func_id = self.db_manager.insert_function(file_id, class_id, func_info)
        if not db_func_id:
            print(f"Error: Failed to insert function '{func_info.name}' into DB.")
            return None
        for param in func_info.parameters:
            print(f"Inserting parameter for function '{func_name}': {param.name}, type={param.type_annotation}, default={param.default_value}")
            self.db_manager.insert_parameter(db_func_id, param)
        for var in func_info.variables:
            self.db_manager.insert_variable(var, function_id=db_func_id)
        for called_name in func_info.calls_made:
            self.db_manager.insert_function_call(db_func_id, called_name, -1)
        print(f"Code Analyzer: Inserted {'method' if class_id else 'top-level function'}: '{func_name}' with ID {db_func_id}.")
        return func_info

    def _visit_class_definition(self, node: Node, source_code_bytes: bytes, file_id: int) -> Optional[ClassInfo]:
        name_node = node.child_by_field_name('name')
        body_node = node.child_by_field_name('body')
        if not name_node:
            return None
        class_name = self._get_node_text(name_node, source_code_bytes)
        start_line = name_node.start_point[0] + 1
        end_line = body_node.end_point[0] + 1 if body_node else name_node.end_point[0] + 1
        docstring = None
        if self.language == 'python' and body_node and body_node.children:
            first_child = body_node.children[0]
            if first_child.type == 'expression_statement' and first_child.children and \
               first_child.children[0].type == 'string':
                docstring = self._get_node_text(first_child.children[0], source_code_bytes).strip('\"\'')
        class_body_content = self._get_node_text(body_node, source_code_bytes) if body_node else None
        class_attributes = []
        if body_node:
            class_attributes = self._extract_variables(body_node, source_code_bytes, is_class_attribute=True)
        current_class_info = ClassInfo(
            name=class_name,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
            body=class_body_content,
            attributes=class_attributes
        )
        db_class_id = self.db_manager.insert_class(file_id, current_class_info)
        if not db_class_id:
            print(f"Error: Failed to insert class '{current_class_info.name}' into DB.")
            return None
        for attr in current_class_info.attributes:
            self.db_manager.insert_variable(attr, class_id=db_class_id)
        if body_node:
            node_type = 'function_definition' if self.language == 'python' else 'method_definition'
            for child in body_node.children:
                if child.type == node_type:
                    method_info = self._visit_function_definition(child, source_code_bytes, file_id, db_class_id)
                    if method_info:
                        current_class_info.methods.append(method_info)
        print(f"Code Analyzer: Inserted class: '{class_name}' with ID {db_class_id}.")
        return current_class_info

    def analyze_code(self, code_string: str, file_path: str) -> Optional[AnalysisResults]:
        print("Code Analyzer: Parsing code...")
        source_code_bytes = code_string.encode('utf8')
        tree = self.parser.parse(source_code_bytes)
        print(f"Code Analyzer: AST Root Node Type: {tree.root_node.type}")
        print(f"Code Analyzer: AST Root Node Text (first 100 chars): {self._get_node_text(tree.root_node, source_code_bytes)[:100]}...")
        checksum = hashlib.md5(source_code_bytes).hexdigest()
        last_modified = datetime.datetime.now().isoformat()
        file_record = self.db_manager.get_file_by_path(file_path)
        file_id = None
        if file_record:
            file_id = file_record[0]
            existing_checksum = file_record[3]
            if existing_checksum == checksum:
                print(f"Code Analyzer: File '{file_path}' already in DB with ID {file_id}. Skipping re-insertion.")
            else:
                print(f"Code Analyzer: File '{file_path}' exists but content changed. Re-analyzing.")
        if not file_id or (file_record and file_record[3] != checksum):
            file_id = self.db_manager.insert_file(file_path, last_modified, checksum, code_string)
            if file_id:
                print(f"Code Analyzer: File '{file_path}' inserted with ID {file_id}.")
            else:
                print(f"Error: Failed to insert file '{file_path}' into DB.")
                return None
        analysis_results = AnalysisResults(file_path=file_path)
        current_scope_variables = self._extract_variables(tree.root_node, source_code_bytes, is_global=True)
        analysis_results.top_level_variables.extend(current_scope_variables)
        for var in current_scope_variables:
            self.db_manager.insert_variable(var, file_id=file_id)
        cursor = tree.walk()
        if cursor.goto_first_child():
            while True:
                node = cursor.node
                if node.type == 'ERROR':
                    print(f"Skipping ERROR node in analyze_code: {self._get_node_text(node, source_code_bytes)}")
                    if not cursor.goto_next_sibling():
                        break
                    continue
                if (self.language == 'python' and node.type == 'function_definition') or \
                   (self.language == 'javascript' and node.type == 'function_declaration'):
                    func_info = self._visit_function_definition(node, source_code_bytes, file_id)
                    if func_info:
                        analysis_results.functions.append(func_info)
                elif self.language == 'javascript' and node.type == 'lexical_declaration':
                    for declarator in node.named_children:
                        if declarator.type == 'variable_declarator':
                            value_node = declarator.child_by_field_name('value')
                            if value_node and value_node.type == 'arrow_function':
                                func_info = self._visit_function_definition(declarator, source_code_bytes, file_id, is_arrow=True)
                                if func_info:
                                    analysis_results.functions.append(func_info)
                elif (self.language == 'python' and node.type == 'class_definition') or \
                     (self.language == 'javascript' and node.type == 'class_declaration'):
                    class_info = self._visit_class_definition(node, source_code_bytes, file_id)
                    if class_info:
                        analysis_results.classes.append(class_info)
                if not cursor.goto_next_sibling():
                    break
        print("Code Analyzer: Code analysis complete.")
        return analysis_results

if __name__ == "__main__":
    import datetime
    class MockDbManager:
        def __init__(self):
            self.files = {}
            self.functions = {}
            self.classes = {}
            self.parameters = {}
            self.variables = {}
            self.function_calls = {}
            self._next_file_id = 1
            self._next_func_id = 1
            self._next_class_id = 1
            self._next_param_id = 1
            self._next_var_id = 1
            self._next_call_id = 1
        def connect(self):
            print("Mock DB: Connected.")
        def close(self):
            print("Mock DB: Closed.")
        def drop_tables(self):
            print("Mock DB: Tables dropped (mock).")
            self.__init__()
        def create_tables(self):
            print("Mock DB: Tables created (mock).")
        def insert_file(self, path: str, last_modified_at: str, checksum: str, full_content: str) -> Optional[int]:
            for file_id, file_data in self.files.items():
                if file_data['path'] == path:
                    print(f"Mock DB: File '{path}' already exists, returning ID {file_id}.")
                    return file_id
            file_id = self._next_file_id
            self.files[file_id] = {'id': file_id, 'path': path, 'last_modified_at': last_modified_at, 'checksum': checksum, 'full_content': full_content}
            self._next_file_id += 1
            print(f"Mock DB: Inserted file '{path}' with ID {file_id}.")
            return file_id
        def get_file_by_path(self, path: str) -> Optional[tuple]:
            for file_id, file_data in self.files.items():
                if file_data['path'] == path:
                    return (file_data['id'], file_data['path'], file_data['last_modified_at'], file_data['checksum'], file_data['full_content'])
            return None
        def insert_function(self, file_id: int, class_id: Optional[int], func_info: FunctionInfo) -> Optional[int]:
            for func_db_id, func_data in self.functions.items():
                if func_data['file_id'] == file_id and func_data['class_id'] == class_id and func_data['name'] == func_info.name:
                    print(f"Mock DB: Function '{func_info.name}' already exists for file ID {file_id}. ID: {func_db_id}")
                    return func_db_id
            func_id = self._next_func_id
            self.functions[func_id] = {'id': func_id, 'file_id': file_id, 'class_id': class_id, 'name': func_info.name,
                                       'start_line': func_info.start_line, 'end_line': func_info.end_line,
                                       'docstring': func_info.docstring, 'body': func_info.body, 'signature': func_info.name + '()'}
            self._next_func_id += 1
            print(f"Mock DB: Inserted function '{func_info.name}' with ID {func_id}.")
            return func_id
        def insert_class(self, file_id: int, class_info: ClassInfo) -> Optional[int]:
            for class_db_id, class_data in self.classes.items():
                if class_data['file_id'] == file_id and class_data['name'] == class_info.name:
                    print(f"Mock DB: Class '{class_info.name}' already exists for file ID {file_id}. ID: {class_db_id}")
                    return class_db_id
            class_id = self._next_class_id
            self.classes[class_id] = {'id': class_id, 'file_id': file_id, 'name': class_info.name,
                                      'start_line': class_info.start_line, 'end_line': class_info.end_line,
                                      'docstring': class_info.docstring, 'body': class_info.body}
            self._next_class_id += 1
            print(f"Mock DB: Inserted class '{class_info.name}' with ID {class_id}.")
            return class_id
        def insert_parameter(self, function_id: int, param_info: ParameterInfo) -> Optional[int]:
            print(f"Mock DB: Inserting parameter '{param_info.name}' for func ID {function_id}, type={param_info.type_annotation}, default={param_info.default_value}")
            param_id = self._next_param_id
            self.parameters[param_id] = {'id': param_id, 'function_id': function_id, 'name': param_info.name,
                                         'type_annotation': param_info.type_annotation, 'default_value': param_info.default_value}
            self._next_param_id += 1
            print(f"Mock DB: Inserted parameter '{param_info.name}' for func ID {function_id}.")
            return param_id
        def insert_variable(self, var_info: VariableInfo, file_id: Optional[int] = None,
                            class_id: Optional[int] = None, function_id: Optional[int] = None) -> Optional[int]:
            var_id = self._next_var_id
            self.variables[var_id] = {'id': var_id, 'file_id': file_id, 'class_id': class_id, 'function_id': function_id,
                                      'name': var_info.name, 'value': var_info.value, 'type_annotation': var_info.type_annotation,
                                      'is_global': var_info.is_global, 'is_class_attribute': var_info.is_class_attribute,
                                      'is_function_local': var_info.is_function_local, 'defined_at_line': var_info.defined_at_line}
            self._next_var_id += 1
            print(f"Mock DB: Inserted variable '{var_info.name}'.")
            return var_id
        def insert_function_call(self, calling_function_id: int, called_name: str, call_line_number: int) -> Optional[int]:
            call_id = self._next_call_id
            self.function_calls[call_id] = {'id': call_id, 'calling_function_id': calling_function_id,
                                            'called_name': called_name, 'call_line_number': call_line_number}
            self._next_call_id += 1
            print(f"Mock DB: Inserted call '{called_name}' from func ID {calling_function_id}.")
            return call_id
        def get_functions_by_file_id(self, file_id: int) -> List[tuple]:
            return [(v['id'], v['file_id'], v['class_id'], v['name'], v['start_line'], v['end_line'], v['docstring'], v['body'], v['signature'])
                    for v in self.functions.values() if v['file_id'] == file_id and v['class_id'] is None]
        def get_classes_by_file_id(self, file_id: int) -> List[tuple]:
            return [(v['id'], v['file_id'], v['name'], v['start_line'], v['end_line'], v['docstring'], v['body'])
                    for v in self.classes.values() if v['file_id'] == file_id]
        def get_methods_by_class_id(self, class_id: int) -> List[tuple]:
            return [(v['id'], v['file_id'], v['class_id'], v['name'], v['start_line'], v['end_line'], v['docstring'], v['body'], v['signature'])
                    for v in self.functions.values() if v['class_id'] == class_id]
        def get_parameters_by_function_id(self, function_id: int) -> List[tuple]:
            print(f"Mock DB: Retrieving parameters for function_id: {function_id}")
            return [(v['id'], v['function_id'], v['name'], v['type_annotation'], v['default_value'])
                    for v in self.parameters.values() if v['function_id'] == function_id]
        def get_variables_by_scope(self, file_id: Optional[int] = None, class_id: Optional[int] = None, function_id: Optional[int] = None) -> List[tuple]:
            results = []
            for v in self.variables.values():
                if file_id is not None and v['file_id'] == file_id and v['class_id'] is None and v['function_id'] is None:
                    results.append((v['id'], v['file_id'], v['class_id'], v['function_id'],
                                    v['name'], v['value'], v['type_annotation'], v['is_global'],
                                    v['is_class_attribute'], v['is_function_local'], v['defined_at_line'], None))
                elif class_id is not None and v['class_id'] == class_id and v['function_id'] is None:
                    results.append((v['id'], v['file_id'], v['class_id'], v['function_id'],
                                    v['name'], v['value'], v['type_annotation'], v['is_global'],
                                    v['is_class_attribute'], v['is_function_local'], v['defined_at_line'], None))
                elif function_id is not None and v['function_id'] == function_id:
                    results.append((v['id'], v['file_id'], v['class_id'], v['function_id'],
                                    v['name'], v['value'], v['type_annotation'], v['is_global'],
                                    v['is_class_attribute'], v['is_function_local'], v['defined_at_line'], None))
            return results
        def get_function_calls_by_calling_function_id(self, calling_function_id: int) -> List[tuple]:
            return [(v['id'], v['calling_function_id'], v['called_name'], v['call_line_number'])
                    for v in self.function_calls.values() if v['calling_function_id'] == calling_function_id]
        def get_all_files(self) -> List[tuple]:
            return [(v['id'], v['path'], v['last_modified_at'], v['checksum'], v['full_content'])
                    for v in self.files.values()]

    print("Starting CodeAnalyzer module test...")
    mock_db = MockDbManager()
    code_analyzer = CodeAnalyzer(language_name="python", db_manager=mock_db)
    sample_code = """
# Test module for CodeAnalyzer
my_global_var = 123
CONST_VALUE: str = "test"
def test_function(param1: int, param2: str = "default"):
    \"\"\"This is a test function.\"\"\"
    local_var = param1 + 5
    print(f"Local var: {local_var}")
    result = another_function(local_var)
    return result
class MyTestClass:
    class_attribute: str = "hello"
    PI: float = 3.14159
    def __init__(self, value):
        self.instance_var = value
        self.log_message("Initialized!")
    def class_method(self, arg):
        \"\"\"A method in MyTestClass.\"\"\"
        method_local_var = arg * 2
        self.log_message(f"Processing {method_local_var}")
        test_function(10)
        return method_local_var
    def log_message(self, msg):
        print(f"[CLASS_LOG]: {msg}")
def another_function(val):
    print(f"Inside another_function with {val}")
    return val * 10
    """
    analysis_results = code_analyzer.analyze_code(sample_code, file_path="/mock/path/to/sample.py")
    if analysis_results:
        print("\n--- Code Analyzer Test Analysis Summary ---")
        print(f"File Path: {analysis_results.file_path}")
        print(f"Top-Level Variables: {[v.name for v in analysis_results.top_level_variables]}")
        print(f"Functions Found: {[f.name for f in analysis_results.functions]}")
        print(f"Classes Found: {[c.name for c in analysis_results.classes]}")
        print("\nDetailed Functions:")
        for func in analysis_results.functions:
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
                    details = f"      - {var.name}"
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
        print("\nDetailed Classes:")
        for cls in analysis_results.classes:
            print(f"  - Class: {cls.name} (Lines {cls.start_line}-{cls.end_line})")
            if cls.docstring:
                print(f"    Docstring: {cls.docstring[:50]}...")
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