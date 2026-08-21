export type PageMeta = { title: string; description: string; canonical: string };

const attr = (selector: string, value: string, attribute = 'content') => {
  const node = document.querySelector(selector);
  if (node) node.setAttribute(attribute, value);
};

/** SPA gezinmesinde başlık ve kanonik adres sayfayla birlikte değişmeli;
 *  tam sayfa yükleme olmadığı için index.html'deki değerler olduğu gibi kalıyordu. */
export const applyMeta = ({ title, description, canonical }: PageMeta) => {
  document.title = title;
  attr('meta[name="description"]', description);
  attr('link[rel="canonical"]', canonical, 'href');
  attr('meta[property="og:title"]', title, 'content');
  attr('meta[property="og:description"]', description, 'content');
  attr('meta[property="og:url"]', canonical, 'content');
  attr('meta[name="twitter:title"]', title, 'content');
  attr('meta[name="twitter:description"]', description, 'content');
};
