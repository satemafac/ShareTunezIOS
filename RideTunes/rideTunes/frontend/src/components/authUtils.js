// authUtils.js

export const checkUserAuthentication = async () => {
  try {
    const response = await fetch('http://localhost:8000/music/api/check_auth/', {
      credentials: 'include',
    });

    if (response.status === 200) {
      return true;
    } else if (response.status === 403) {
      return false;
    } else {
      console.error('Unexpected response status:', response.status);
      return false;
    }
  } catch (error) {
    console.error('Error checking authentication:', error);
    return false;
  }
};


  