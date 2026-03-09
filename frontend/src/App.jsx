import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Layout
import Layout from './components/Layout';

// Pages
import Dashboard from './pages/Dashboard';
import Trading from './pages/Trading';
import Settings from './pages/Settings';

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, // Data is fresh for 5 seconds
      retry: 2, // Retry failed requests twice
      refetchOnWindowFocus: false, // Don't refetch on window focus
    },
  },
});

/**
 * Main App component with routing and providers
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Main layout with nested routes */}
          <Route path="/" element={<Layout />}>
            {/* Dashboard - default route */}
            <Route index element={<Dashboard />} />

            {/* Trading page */}
            <Route path="trading" element={<Trading />} />

            {/* Settings page */}
            <Route path="settings" element={<Settings />} />

            {/* Catch-all redirect to dashboard */}
            <Route path="*" element={<Dashboard />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
