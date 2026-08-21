import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Router gezinmesinde tarayıcı kaydırmayı korur; yeni sayfa ortasından açılmasın.
 *  /panel/<slug> kendi odak kaydırmasını yaptığı için burada dokunulmaz. */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pathname.startsWith('/panel/')) return;
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [pathname]);
  return null;
}

export default ScrollToTop;
