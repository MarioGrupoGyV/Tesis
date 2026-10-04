import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, type User } from '../../lib/api';

/** One view lifetime owns its writes. Leaving a context discards late answers. */
export function useFollowupWrite(user: User) {
  const cache = useQueryClient();
  const alive = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState('');
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; controller.current?.abort(); };
  }, []);
  async function submit<T>(operation: (signal: AbortSignal) => Promise<T>, onSuccess: (result: T) => void) {
    if (busy.current) return;
    busy.current = true;
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    setPending(true); setError(null); setSuccess('');
    try {
      const result = await operation(request.signal);
      if (!alive.current || request.signal.aborted) return;
      onSuccess(result);
      await cache.invalidateQueries({ queryKey: [user.id, user.role] });
    } catch (failure) {
      if (alive.current && !request.signal.aborted && !(failure instanceof DOMException && failure.name === 'AbortError')) setError(failure);
    } finally { busy.current = false; if (alive.current && !request.signal.aborted) setPending(false); }
  }
  const uncertain = error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.status === 503);
  const conflict = error instanceof ApiError && error.status === 409;
  return { pending, error, success, uncertain, conflict, submit, setError, setSuccess };
}

export function ConflictReview({ reviewed, refreshed, refreshing, onRefresh, onReviewed, subject }: {
  reviewed: boolean; refreshed: boolean; refreshing: boolean; onRefresh: () => void; onReviewed: (value: boolean) => void; subject: 'caso' | 'actividad';
}) {
  return <div className="notice" role="status"><strong>Conservamos tu borrador</strong><p>El recurso cambió o existe un conflicto. Consulta su estado actualizado y revísalo antes de enviar una nueva solicitud. Los cambios de otra persona no se sobrescriben automáticamente.</p><button className="button secondary" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Consultando cambios…' : `Revisar cambios del ${subject === 'caso' ? 'caso' : 'registro de actividad'}`}</button>{refreshed && <p>La información actualizada se muestra junto al formulario. Tu borrador permanece sin cambios.</p>}<label className="followup-checkbox"><input type="checkbox" checked={reviewed} disabled={refreshing || !refreshed} onChange={event => onReviewed(event.target.checked)} />He revisado el recurso actualizado</label></div>;
}
