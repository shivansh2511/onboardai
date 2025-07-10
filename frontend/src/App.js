import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';
import Chart from 'chart.js/auto';
import Tree from 'react-d3-tree';
import './App.css';

function App() {
  const [analysisData, setAnalysisData] = useState([]);
  const [error, setError] = useState(null);
  const [languageFilter, setLanguageFilter] = useState('all');
  const [classFilter, setClassFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [fileContents, setFileContents] = useState({});

  useEffect(() => {
    axios
      .get('http://localhost:3000/api/analysis')
      .then((response) => {
        setAnalysisData(response.data);
        response.data.forEach((file) => {
          const fileName = file.file_path.split('/').pop(); // Extract filename
          axios
            .get(`http://localhost:3000/api/file/${fileName}`)
            .then((res) => {
              setFileContents((prev) => ({
                ...prev,
                [file.file_path]: res.data,
              }));
            })
            .catch((err) => {
              console.error(`Failed to fetch ${fileName}:`, err);
              setFileContents((prev) => ({
                ...prev,
                [file.file_path]: 'Error loading file content',
              }));
            });
        });
      })
      .catch((err) => {
        setError('Failed to fetch analysis data');
        console.error(err);
      });
  }, []);

  const chartData = {
    labels: analysisData
      .filter((file) => languageFilter === 'all' || file.file_path.endsWith(languageFilter))
      .filter((file) => classFilter === 'all' || (classFilter === 'hasClasses' && file.classes.length > 0))
      .filter((file) => file.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
      .map((file) => file.file_path.split('/').pop()),
    datasets: [
      {
        label: 'Number of Functions',
        data: analysisData
          .filter((file) => languageFilter === 'all' || file.file_path.endsWith(languageFilter))
          .filter((file) => classFilter === 'all' || (classFilter === 'hasClasses' && file.classes.length > 0))
          .filter((file) => file.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
          .map((file) => file.functions.length),
        backgroundColor: ['#4CAF50', '#2196F3', '#FFC107', '#F44336', '#9C27B0'],
      },
    ],
  };

  const buildTreeData = (file) => ({
    name: file.file_path.split('/').pop(),
    children: [
      {
        name: 'Variables',
        children: file.top_level_variables.map((v) => ({
          name: `${v.name}${v.type ? `: ${v.type}` : ''}`,
        })),
      },
      {
        name: 'Functions',
        children: file.functions.map((f) => ({
          name: f.name,
          children: [
            { name: `Parameters: ${f.parameters.map((p) => p.name).join(', ') || 'None'}` },
            { name: `Local Vars: ${f.local_vars.map((v) => v.name).join(', ') || 'None'}` },
          ],
        })),
      },
      {
        name: 'Classes',
        children: file.classes.map((c) => ({
          name: c.name,
          children: [
            {
              name: 'Attributes',
              children: c.attributes.map((a) => ({
                name: `${a.name}${a.type ? `: ${a.type}` : ''}`,
              })),
            },
            {
              name: 'Methods',
              children: c.methods.map((m) => ({
                name: m.name,
              })),
            },
          ],
        })),
      },
    ],
  });

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="App">
      <h1>OnboardAI Dashboard</h1>
      <div className="filter">
        <label>Search Files: </label>
        <input
          type="text"
          placeholder="Enter file name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>
      <div className="filter">
        <label>Filter by Language: </label>
        <select onChange={(e) => setLanguageFilter(e.target.value)}>
          <option value="all">All</option>
          <option value=".py">Python</option>
          <option value=".ts">TypeScript</option>
          <option value=".js">JavaScript</option>
        </select>
      </div>
      <div className="filter">
        <label>Filter by Classes: </label>
        <select onChange={(e) => setClassFilter(e.target.value)}>
          <option value="all">All</option>
          <option value="hasClasses">Has Classes</option>
        </select>
      </div>
      <div className="chart">
        <h3>Functions per File</h3>
        <Bar
          data={chartData}
          options={{
            scales: {
              y: {
                beginAtZero: true,
                title: { display: true, text: 'Functions' },
              },
            },
            plugins: {
              title: { display: true, text: 'Functions per File' },
            },
          }}
        />
      </div>
      {analysisData.length === 0 ? (
        <p>Loading...</p>
      ) : (
        analysisData
          .filter((file) => languageFilter === 'all' || file.file_path.endsWith(languageFilter))
          .filter((file) => classFilter === 'all' || (classFilter === 'hasClasses' && file.classes.length > 0))
          .filter((file) => file.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
          .map((file, index) => (
            <div key={index} className="file-section">
              <h2>File: {file.file_path}</h2>
              <h3>Code Content</h3>
              <pre className="code-snippet">
                {fileContents[file.file_path] || 'Loading content...'}
              </pre>
              <h3>Code Structure Tree</h3>
              <div className="tree">
                <Tree
                  data={buildTreeData(file)}
                  orientation="vertical"
                  translate={{ x: 300, y: 50 }}
                  zoom={0.8}
                />
              </div>
              <h3>Variables</h3>
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Value</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {file.top_level_variables.map((varInfo, varIndex) => (
                    <tr key={varIndex}>
                      <td>{varInfo.name}</td>
                      <td>{varInfo.value || 'N/A'}</td>
                      <td>{varInfo.type || 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Functions</h3>
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Lines</th>
                    <th>Parameters</th>
                    <th>Local Variables</th>
                    <th>Calls</th>
                  </tr>
                </thead>
                <tbody>
                  {file.functions.map((func, funcIndex) => (
                    <tr key={funcIndex}>
                      <td>{func.name}</td>
                      <td>
                        {func.start_line}-{func.end_line}
                      </td>
                      <td>
                        {func.parameters
                          .map(
                            (param) =>
                              `${param.name}${param.type ? `: ${param.type}` : ''}${
                                param.default ? ` = ${param.default}` : ''
                              }`
                          )
                          .join(', ') || 'None'}
                      </td>
                      <td>
                        {func.local_vars.map((v) => v.name).join(', ') || 'None'}
                      </td>
                      <td>{func.calls.join(', ') || 'None'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Classes</h3>
              {file.classes.length === 0 ? (
                <p>No classes</p>
              ) : (
                file.classes.map((cls, clsIndex) => (
                  <div key={clsIndex}>
                    <h4>Class: {cls.name}</h4>
                    <p>
                      Lines: {cls.start_line}-{cls.end_line}
                    </p>
                    <h5>Attributes</h5>
                    <table>
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Value</th>
                          <th>Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cls.attributes.map((attr, attrIndex) => (
                          <tr key={attrIndex}>
                            <td>{attr.name}</td>
                            <td>{attr.value || 'N/A'}</td>
                            <td>{attr.type || 'N/A'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <h5>Methods</h5>
                    <table>
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Parameters</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cls.methods.map((method, methodIndex) => (
                          <tr key={methodIndex}>
                            <td>{method.name}</td>
                            <td>
                              {method.parameters
                                .map(
                                  (param) =>
                                    `${param.name}${param.type ? `: ${param.type}` : ''}`
                                )
                                .join(', ') || 'None'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))
              )}
            </div>
          ))
      )}
    </div>
  );
}

export default App;