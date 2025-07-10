const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

app.get('/api/analysis', (req, res) => {
  try {
    const data = fs.readFileSync(
      path.join(__dirname, '../analysis_output.json'),
      'utf8'
    );
    res.json(JSON.parse(data));
  } catch (err) {
    console.error('Error reading analysis_output.json:', err);
    res.status(500).json({ error: 'Failed to read analysis data' });
  }
});

app.get('/api/file/:fileName', (req, res) => {
  const filePath = path.join(__dirname, '..', 'src', 'sample_codes', req.params.fileName);
  console.log(`Requested file path: ${filePath}`); // Debug log
  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf8');
      res.send(content);
    } else {
      res.status(404).json({ error: `File not found: ${filePath}` });
    }
  } catch (err) {
    console.error('Error reading file:', err);
    res.status(500).json({ error: `Failed to read file: ${err.message}` });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});