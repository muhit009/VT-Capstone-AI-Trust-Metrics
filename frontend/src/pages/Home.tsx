import { Navigate } from 'react-router-dom';

function Home() {
  return <Navigate to="/dashboard/chat" replace />;
}

export default Home;