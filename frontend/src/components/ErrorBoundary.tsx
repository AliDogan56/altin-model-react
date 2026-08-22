import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode; title?: string };
type State = { error: Error | null };

/**
 * Tek bir bölümün hatası tüm siteyi düşürmesin.
 *
 * Sınır yokken, sunucudan gelen bozuk bir tahmin yanıtı
 * `forecast.horizons.indexOf(...)` üzerinden fırlıyor ve React tüm ağacı
 * söküyordu: sayfa gövdesi tamamen boş kalıyordu (deneyle doğrulandı).
 */
class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Bölüm hatası:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <section className="panel block error-fallback" role="alert">
        <h2>{this.props.title ?? 'Bu bölüm yüklenemedi'}</h2>
        <p>Beklenmeyen bir hata oluştu; sayfanın geri kalanı çalışmaya devam ediyor.
          Sorun sürerse sayfayı yenileyin.</p>
        <div className="error-actions">
          <button type="button" className="primary" onClick={() => this.setState({ error: null })}>
            Yeniden dene</button>
          <button type="button" onClick={() => window.location.reload()}>Sayfayı yenile</button>
        </div>
        <details><summary>Teknik ayrıntı</summary><pre>{error.message}</pre></details>
      </section>
    );
  }
}

export default ErrorBoundary;
