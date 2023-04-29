import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Music from './components/Music'; 

const App = () => {
  return (
    <Router>
      <Routes>
        {/* Your other routes, if any */}
        <Route path="/music" element={<Music />} />
      </Routes>
    </Router>
  );
};

export default App;
