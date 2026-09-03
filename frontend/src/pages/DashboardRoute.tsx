import ErrorBoundary from '../components/ErrorBoundary';
import { DashboardProvider } from '../features/dashboard/DashboardContext';
import DashboardPage from './DashboardPage';

/** Panel rotası tek parça: sağlayıcı (socket.io, veri kancaları) ve sayfa birlikte
 *  tembel yüklenir; rehber sayfaları bu kodu hiç indirmez. Panel durumu yalnız
 *  burada kurulur — rehber sayfaları soket açmaz. */
function DashboardRoute({ focus }: { focus?: string }) {
  return (
    <ErrorBoundary title="Panel yüklenemedi">
      <DashboardProvider><DashboardPage focus={focus}/></DashboardProvider>
    </ErrorBoundary>
  );
}

export default DashboardRoute;
