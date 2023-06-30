import React from 'react';
import { BrowserRouter as Router, Route, Routes, Switch } from 'react-router-dom';
import Music from './components/Music';
import Share from './components/Share'; // import the Share component

const App = () => {
  return (
    <Router>
      <Routes>
        {/* Your other routes, if any */}
        <Route path="/music" element={<Music />} />
        <Route path="/music/share/:provider/:username/:id" element={<Share />} />
      </Routes>
    </Router>
  );
};

export default App;
