import { useEffect } from 'react';
import { useParams, type Params } from 'react-router-dom';

/**
 * Full-page redirect to another app (outside this router's basename). `to` is a
 * builder over the route params so old bookmarks land on the same resource.
 * Renders nothing — the navigation is immediate.
 */
export function ExternalRedirect({ to }: { to: (params: Readonly<Params<string>>) => string }) {
  const params = useParams();
  useEffect(() => {
    window.location.replace(to(params));
  }, [to, params]);
  return null;
}
