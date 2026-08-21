import { useEffect } from 'react';
import { SITE_NAME } from '../content/site';
import { applyMeta } from '../lib/meta';

export const useDocumentMeta = (title: string, description: string, path: string, enabled = true) => {
  useEffect(() => {
    if (!enabled) return;
    applyMeta({ title: `${title} | ${SITE_NAME}`, description, canonical: `${window.location.origin}${path}` });
  }, [title, description, path, enabled]);
};
