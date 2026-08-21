import raw from './model.json';
import type { ModelArtifact } from '../domain/model/types';

/** Eğitilmiş ağırlıklar. Domain katmanı bu dosyayı import etmez; artefakt
 *  parametre olarak geçirilir, böylece saf ve test edilebilir kalır. */
export const model = raw as unknown as ModelArtifact;
