import os
import sys
import argparse
import json
import glob
import datetime
from typing import List, Optional
from .database.sqlite_manager import SQLiteManager

def get_file_extension_and_language(file_path: str) -> tuple[str, str]:
    """Determine the language and file extension for a given file path."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".py":
        return "python", "py"
    elif extension in [".ts", ".tsx"]:
        return "javascript", "ts"
    elif extension in [".js", ".jsx"]:
        return "javascript", "js"
    return None, ""

def analyze_file(file_path: str, db_manager: SQLiteManager) -> Optional['AnalysisResults']:
    """Analyze a single file and return the analysis results."""
    language, file_extension = get_file_extension_and_language(file_path)
    if not language:
        print(f"Skipping unsupported file: {file_path}")
        return None
    try:
        from .code_analyzer import CodeAnalyzer, AnalysisResults
        with open(file_path, encoding="utf-8") as file:
            code = file.read()
        analyzer = CodeAnalyzer(language_name=language, db_manager=db_manager, file_extension=file_extension)
        return analyzer.analyze_code(code, file_path)
    except ImportError as e:
        print(f"Import error for code_analyzer: {e}")
        print(f"Ensure 'code_analyzer.py' exists in {os.path.dirname(__file__)} and dependencies are installed.")
        return None
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None

def print_analysis_summary(analysis_results: 'AnalysisResults'):
    """Print the analysis summary for a file."""
    print(f"\n--- Analysis Summary for {analysis_results.file_path} ---")
    print(f"Module Docstring: {analysis_results.module_docstring or 'N/A'}")
    print(f"Top-Level Variables: {[variable.name for variable in analysis_results.top_level_variables]}")
    print(f"Functions Found: {[function.name for function in analysis_results.functions]}")
    print(f"Classes Found: {[class_.name for class_ in analysis_results.classes]}")
    print("\nDetailed Functions:")
    for function in analysis_results.functions:
        print(f"  - Function: {function.name} (Lines {function.start_line}-{function.end_line})")
        if function.docstring:
            print(f"    Docstring: {function.docstring[:50]}...")
        if function.parameters:
            print("    Parameters:")
            for parameter in function.parameters:
                parameter_details = f"      - {parameter.name}"
                if parameter.type_annotation:
                    parameter_details += f": {parameter.type_annotation}"
                if parameter.default_value:
                    parameter_details += f" = {parameter.default_value}"
                print(parameter_details)
        if function.variables:
            print("    Local Variables:")
            for variable in function.variables:
                details = f"      - {variable.name}"
                if variable.value:
                    details += f" = {variable.value}"
                print(details)
        if function.calls_made:
            print(f"      Calls:")
            for call in function.calls_made:
                print(f"      - {call}")
    print("\nDetailed Classes:")
    for class_ in analysis_results.classes:
        print(f"  - Class: {class_.name} (Lines {class_.start_line}-{class_.end_line})")
        if class_.docstring:
            print(f"    Docstring: {class_.docstring[:50]}...")
        if class_.attributes:
            print("    Class Attributes:")
            for attribute in class_.attributes:
                details = f"      - {attribute.name}"
                if attribute.type_annotation:
                    details += f": {attribute.type_annotation}"
                if attribute.value:
                    details += f" = {attribute.value}"
                print(details)
        if class_.methods:
            print("    Methods:")
            for method in class_.methods:
                print(f"      - Method: {method.name} (Lines {method.start_line}-{method.end_line})")

def save_to_json(analysis_results_list: List['AnalysisResults'], output_file: str):
    """Save analysis results to a JSON file."""
    results = []
    for analysis_results in analysis_results_list:
        result = {
            "file_path": analysis_results.file_path,
            "module_docstring": analysis_results.module_docstring,
            "top_level_variables": [
                {"name": variable.name, "value": variable.value, "type": variable.type_annotation}
                for variable in analysis_results.top_level_variables
            ],
            "functions": [
                {
                    "name": function.name,
                    "start_line": function.start_line,
                    "end_line": function.end_line,
                    "parameters": [
                        {"name": parameter.name, "type": parameter.type_annotation, "default": parameter.default_value}
                        for parameter in function.parameters
                    ],
                    "local_vars": [
                        {"name": variable.name, "value": variable.value}
                        for variable in function.variables
                    ],
                    "calls": function.calls_made
                }
                for function in analysis_results.functions
            ],
            "classes": [
                {
                    "name": class_.name,
                    "start_line": class_.start_line,
                    "end_line": class_.end_line,
                    "attributes": [
                        {"name": attribute.name, "value": attribute.value, "type": attribute.type_annotation}
                        for attribute in class_.attributes
                    ],
                    "methods": [
                        {
                            "name": method.name,
                            "parameters": [
                                {"name": parameter.name, "type": parameter.type_annotation}
                                for parameter in method.parameters
                            ]
                        }
                        for method in class_.methods
                    ]
                }
                for class_ in analysis_results.classes
            ]
        }
        results.append(result)
    
    with open(output_file, 'w') as file:
        json.dump(results, file, indent=2)
    print(f"Saved analysis to {output_file}")

def main():
    """Main function to run the OnboardAI MVP demo with CLI."""
    print("Starting OnboardAI MVP Demo (inside main function)...")
    parser = argparse.ArgumentParser(description="OnboardAI MVP: CLI Analysis Tool")
    parser.add_argument(
        "--directory",
        type=str,
        default="src/sample_codes",
        help="Directory containing code files to analyze"
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="python,typescript",
        help="Comma-separated languages to analyze (python,typescript,javascript)"
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["console", "json"],
        default="console",
        help="Output format (console or json)"
    )
    arguments = parser.parse_args()

    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    database_path = os.path.join(data_dir, 'onboardai.db')
    database_manager = SQLiteManager(database_path)

    # Debug: Check for code_analyzer.py
    code_analyzer_path = os.path.join(os.path.dirname(__file__), 'code_analyzer.py')
    if not os.path.exists(code_analyzer_path):
        print(f"Error: 'code_analyzer.py' not found at {code_analyzer_path}")
        print(f"Current sys.path: {sys.path}")
        print("Please ensure 'code_analyzer.py' exists in the 'src' directory.")
        return

    database_manager.connect()
    database_manager.drop_tables()
    database_manager.create_tables()

    print("\n--- Analyzing Sample Code ---")
    languages_list = [lang.strip().lower() for lang in arguments.languages.split(",")]
    extensions = []
    if "python" in languages_list:
        extensions.append("*.py")
    if "typescript" in languages_list or "javascript" in languages_list:
        extensions.extend(["*.ts", "*.tsx", "*.js", "*.jsx"])

    files_list = []
    for extension in extensions:
        files_list.extend(glob.glob(os.path.join(arguments.directory, extension)))

    analysis_results_list = []
    for file_path in files_list:
        print(f"Processing file: {file_path}...")
        analysis_results = analyze_file(file_path, database_manager)
        if analysis_results:
            analysis_results_list.append(analysis_results)
            if arguments.output == "console":
                print_analysis_summary(analysis_results)

    if arguments.output == "json":
        save_to_json(analysis_results_list, "analysis_output.json")

    print("\n--- Testing Database Retrieval ---")
    print("\nFiles in Database:")
    for file_record in database_manager.get_all_files():
        file_id, file_path, _, checksum, _ = file_record
        print(f"  File ID: {file_id}, Path: {file_path}, Checksum: {checksum}")
        variables = database_manager.get_variables_by_scope(file_id=file_id)
        if variables:
            print("  Top-Level Variables:")
            for variable in variables:
                variable_name = variable[4]
                variable_value = variable[5]
                variable_type = variable[6]
                details = f"    - {variable_name}"
                if variable_value:
                    details += f" = {variable_value}"
                if variable_type:
                    details += f" (Type: {variable_type})"
                print(details)
        functions = database_manager.get_functions_by_file_id(file_id)
        if functions:
            print("  Functions (Top-Level):")
            for function in functions:
                function_id, _, _, function_name, start_line, end_line, _, _, _ = function
                print(f"    - Function ID: {function_id}, Name: {function_name}, Lines: {start_line}-{end_line}")
                print(f"Database: Retrieving parameters for function_id={function_id}")
                parameters = database_manager.get_parameters_by_function_id(function_id)
                print(f"Database: Retrieved {len(parameters)} parameters for function_id={function_id}: {parameters}")
                if parameters:
                    print("      Parameters:")
                    for parameter in parameters:
                        _, _, parameter_name, parameter_type, parameter_default = parameter
                        parameter_details = f"        - {parameter_name}"
                        if parameter_type:
                            parameter_details += f": {parameter_type}"
                        if parameter_default:
                            parameter_details += f" = {parameter_default}"
                        print(parameter_details)
                variables = database_manager.get_variables_by_scope(function_id=function_id)
                if variables:
                    print("      Local Variables:")
                    for variable in variables:
                        variable_name = variable[4]
                        variable_value = variable[5]
                        variable_type = variable[6]
                        details = f"        - {variable_name}"
                        if variable_value:
                            details += f" = {variable_value}"
                        if variable_type:
                            details += f" (Type: {variable_type})"
                        print(details)
                calls = database_manager.get_function_calls_by_calling_function_id(function_id)
                if calls:
                    print("      Calls Made:")
                    for call in calls:
                        print(f"        - {call[2]}")

    database_manager.close()
    print("\nOnboardAI MVP Demo Finished.")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()