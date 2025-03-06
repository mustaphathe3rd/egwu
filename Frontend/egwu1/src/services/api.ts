import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL; //http://localhost:8000 

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  }
});

// Request interceptor to add Authorization header
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Enhanced token refresh
export const refreshToken = async (): Promise<boolean> => {
  try {
    const refresh_token = localStorage.getItem('refresh_token');
    if (!refresh_token) return false;

    const response = await axios.post(`${API_BASE_URL}/token/refresh/`, {
      refresh: refresh_token
    });

    if (response.data.access) {
      localStorage.setItem('access_token', response.data.access);
      return true;
    }
    return false;
  } catch (error) {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return false;
  }
};

// Response interceptor for handling token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (!originalRequest) return Promise.reject(error);

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshSuccessful = await refreshToken();
        if (refreshSuccessful) {
          originalRequest.headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Authentication check
export const checkAuth = async (): Promise<boolean> => {
  try {
    await api.get('/verify/');
    return true;
  } catch {
    return false;
  }
};

// Processing status check with retry logic
export const checkProcessingStatus = async () => {
  const maxRetries = 3;
  let retryCount = 0;

  const checkStatus = async () => {
    try {
      const response = await api.get('/processing-status/');
      return response.data;
    } catch (error) {
      if (retryCount < maxRetries) {
        retryCount++;
        await new Promise(resolve => setTimeout(resolve, 1000 * retryCount));
        return checkStatus();
      }
      throw error;
    }
  };

  return checkStatus();
};

export default api;
