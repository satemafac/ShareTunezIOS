import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkUserAuthentication } from './authUtils';

const ProtectedComponent = ({ children }) => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuthentication = async () => {
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Add a delay of 1 second
      // Add 'await' before calling 'checkUserAuthentication()'
      if (!await checkUserAuthentication()) {
        window.location.href = 'http://localhost:8000/music/login'; // Redirect to the Django login page if not authenticated
      } else {
        setIsLoading(false);
      }
    };

    checkAuthentication();
  }, [navigate]);

  return isLoading ? <div>Loading...</div> : children;
};

export default ProtectedComponent;
