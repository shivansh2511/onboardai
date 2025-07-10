OnboardAI
OnboardAI is a tool designed to simplify onboarding for new developers by analyzing codebases and presenting key information in an intuitive web dashboard. It helps new joiners understand critical files, variables, functions, and classes without needing senior developer assistance. The tool supports Python, TypeScript, and JavaScript files and provides:

Code Snippets: View raw code of each file.
Tables: Detailed lists of variables, functions, and classes with types, parameters, and line numbers.
Visualizations: Bar charts showing function counts and tree diagrams for code structure.
Filters: Search by file name or filter by language (Python, TypeScript, JavaScript) and classes.

This project is ideal for companies onboarding new developers, enabling them to explore codebases independently. Future updates will include AI-powered code explanations.
Project Structure
onboardai/
├── backend/              # Node.js/Express server
│   ├── server.js         # API endpoints for analysis and file content
│   ├── package.json      # Backend dependencies
├── frontend/             # React web dashboard
│   ├── src/
│   │   ├── App.js        # Main React component
│   │   ├── App.css       # Dashboard styles
│   ├── package.json      # Frontend dependencies
├── src/
│   ├── sample_codes/     # Sample code files for analysis
│   │   ├── test1.py      # Example Python file
│   │   ├── test2.py      # Example Python file
│   │   ├── test.ts       # Example TypeScript file
│   ├── main.py           # CLI script for code analysis
├── analysis_output.json  # Output of CLI analysis
├── .gitignore            # Ignored files (node_modules, .venv, etc.)
├── README.md             # This file

Prerequisites
Before running OnboardAI, install:

Node.js (v16 or higher, tested with v22.9.0): Download
Python (3.8 or higher): Download
Git: Download
A web browser (e.g., Chrome, Firefox).

Installation
Follow these steps to set up and run OnboardAI on your system:

Clone the Repository:
git clone https://github.com/your-username/onboardai.git
cd onboardai

Replace your-username with your GitHub username.

Set Up Python Virtual Environment:
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate


Install Python Dependencies:The CLI uses tree-sitter for code parsing:
pip install tree-sitter


Install Backend Dependencies:
cd backend
npm install


Install Frontend Dependencies:
cd ../frontend
npm install



Running the Project

Generate Analysis Data:Run the CLI to analyze code in src/sample_codes and generate analysis_output.json:
cd /path/to/onboardai
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python3 -m src.main --directory src/sample_codes --languages typescript,python --output json

This analyzes test1.py, test2.py, test.ts and creates analysis_output.json.

Start the Backend Server:
cd backend
npm start


Output: Server running at http://localhost:3000.
Provides APIs:
http://localhost:3000/api/analysis: Returns analysis data.
http://localhost:3000/api/file/test1.py: Returns file content.




Start the Frontend Dashboard:In a new terminal:
cd /path/to/onboardai/frontend
npm start


Opens http://localhost:3000 (or another port if prompted).
Displays the dashboard with snippets, tables, charts, and trees.


Explore the Dashboard:

Code Snippets: View raw code (e.g., def func1: in test1.py).
Tables: See variables (e.g., VAR1: int), functions (e.g., func1), and classes (e.g., MyClass).
Filters: Search by file name or filter by language or classes.
Charts/Trees: Visualize function counts and code structure.



Troubleshooting

Server Fails to Start:

Verify express@4.17.1 and cors@2.8.5 in backend/package.json.
Run cd backend; npm install.
Check terminal output and share errors.


Snippets Show “Error loading file content”:

Ensure src/sample_codes contains test1.py, test2.py, test.ts.
Verify analysis_output.json has correct paths (e.g., src/sample_codes/test1.py).
Check browser Console (F12) for errors and share them.


CLI Fails:

Ensure tree-sitter is installed: pip install tree-sitter.
Verify src/main.py and sample files exist.


CORS Errors:

Ensure backend uses cors({ origin: 'http://localhost:3000' }).
Match frontend port in server.js if different.



Example Usage

Run CLI to analyze your own codebase:python3 -m src.main --directory path/to/your/code --languages typescript,python --output json


Update server.js to point to your code directory if needed.
Restart backend and frontend to view analysis.

Future Improvements

AI Explanations: Integrate a Large Language Model (e.g., Gemini API) to provide natural language summaries of code and prioritize important files.
Syntax Highlighting: Add react-syntax-highlighter for better code readability.
Deployment: Host on Vercel/Heroku for team access.

Contributing

Fork the repository.
Create a branch: git checkout -b feature-name.
Commit changes: git commit -m "Add feature".
Push: git push origin feature-name.
Open a pull request.

License
MIT License. See LICENSE for details (add a LICENSE file if desired).
Contact
For issues or suggestions, open a GitHub issue or contact [your-email@example.com].