import { useId } from 'react';

/**
 * Projeye özgü yükleme göstergesi: uygulama ikonundaki altın sikke, aşağıdan
 * yukarı **doluyor**. Üstünde ikonun analiz oku çiziliyor ve sikke kenarında
 * klasik dönen yay var — üçü birlikte hem "yükleniyor" hem "altın" okunur.
 *
 * Gradyan ve kırpma yolu kimlikleri `useId` ile üretilir; aynı sayfada birden
 * çok spinner olduğunda sabit id'ler birbirini eziyor ve ilk spinner dışındakiler
 * dolgusuz kalıyordu.
 *
 * Hareket `prefers-reduced-motion` altında durur; sikke yarı dolu sabit kalır.
 */

type Size = 'xs' | 'sm' | 'md' | 'lg';

const PX: Record<Size, number> = { xs: 12, sm: 16, md: 22, lg: 44 };

function Spinner({ size = 'md', label, inline = false }: {
  size?: Size;
  /** Yanına yazılacak metin. Verilirse ekran okuyucu bunu duyurur. */
  label?: string;
  /** Metinle aynı satırda akmasını istiyorsan. */
  inline?: boolean;
}) {
  const uid = useId().replace(/:/g, '');
  const px = PX[size];

  const icon = (
    <svg className={`spinner-icon spinner-${size}`} viewBox="0 0 32 32"
      width={px} height={px} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${uid}-fill`} x1="0" y1="30" x2="0" y2="4" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--spinner-deep)"/>
          <stop offset=".55" stopColor="var(--spinner-mid)"/>
          <stop offset="1" stopColor="var(--spinner-light)"/>
        </linearGradient>
        {/* Dolgu yalnız sikkenin içinde görünsün. */}
        <clipPath id={`${uid}-coin`}><circle cx="16" cy="16" r="11.5"/></clipPath>
      </defs>

      {/* Sikke gövdesi */}
      <circle className="spinner-well" cx="16" cy="16" r="11.5"/>

      {/* Yükselen altın: dikdörtgen sikkenin içinde aşağıdan yukarı kayar. */}
      <g clipPath={`url(#${uid}-coin)`}>
        <g className="spinner-rise">
          <rect x="0" y="4" width="32" height="30" fill={`url(#${uid}-fill)`}/>
          {/* Yüzeydeki hafif dalga, dolumun sıvı gibi okunmasını sağlıyor. */}
          <path className="spinner-wave" d="M-24 4q8-3 16 0t16 0t16 0t16 0v8h-64z" fill="var(--spinner-light)"/>
        </g>
      </g>

      {/* İkonun analiz oku: dolum ilerledikçe çizilir. */}
      <g className="spinner-mark">
        <path d="M9.5 20l4.5-4.5 3 2.5 6.5-7"/>
        <path d="M20 11h3.5v3.5"/>
      </g>

      {/* Sikke kenarı ve üzerinde dönen yay */}
      <circle className="spinner-rim" cx="16" cy="16" r="11.5"/>
      <circle className="spinner-arc" cx="16" cy="16" r="11.5"/>
    </svg>
  );

  if (!label) {
    return <span className={`spinner${inline ? ' inline' : ''}`} role="status"
      aria-label="Yükleniyor">{icon}</span>;
  }

  return (
    <span className={`spinner${inline ? ' inline' : ''}`} role="status">
      {icon}<span className="spinner-label">{label}</span>
    </span>
  );
}

export default Spinner;
