import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { checkUserAuthentication } from './authUtils';

const ProtectedComponent = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuthentication = async () => {
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Add a delay of 1 second
      // Add 'await' before calling 'checkUserAuthentication()'
      if (!await checkUserAuthentication()) {
        sessionStorage.setItem('preLoginRoute', location.pathname); // Store the current location before redirecting
        window.location.href = 'http://localhost:8000/music/login'; // Redirect to the Django login page if not authenticated
      } else {
        setIsLoading(false);
      }
    };

    checkAuthentication();
  }, [navigate, location.pathname]);

  return isLoading ? <div>Loading...</div> : children;
};

export default ProtectedComponent;
