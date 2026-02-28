import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EventList } from './components/EventList';
import { EventDetail } from './components/EventDetail';
import { ReviewQueue } from './components/ReviewQueue';
import { Dashboard } from './components/Dashboard';
import { ConfigPage } from './components/ConfigPage';
import { ExportPage } from './components/ExportPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          <header className="bg-white shadow-sm border-b">
            <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
              <h1 className="text-xl font-semibold text-gray-900">
                <a href="/" className="hover:text-blue-600">Event Deduplication</a>
              </h1>
              <nav className="flex gap-4">
                <Link to="/" className="text-sm text-gray-600 hover:text-blue-600">
                  Events
                </Link>
                <Link to="/review" className="text-sm text-gray-600 hover:text-blue-600">
                  Review Queue
                </Link>
                <Link to="/dashboard" className="text-sm text-gray-600 hover:text-blue-600">
                  Dashboard
                </Link>
                <Link to="/config" className="text-sm text-gray-600 hover:text-blue-600">
                  Config
                </Link>
                <Link to="/export" className="text-sm text-gray-600 hover:text-blue-600">
                  Export
                </Link>
              </nav>
            </div>
          </header>
          <main className="max-w-7xl mx-auto px-4 py-6">
            <Routes>
              <Route path="/" element={<EventList />} />
              <Route path="/events/:id" element={<EventDetail />} />
              <Route path="/review" element={<ReviewQueue />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/config" element={<ConfigPage />} />
              <Route path="/export" element={<ExportPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
