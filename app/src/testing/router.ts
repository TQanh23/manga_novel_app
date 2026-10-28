import { renderRouter } from 'expo-router/testing-library';

type Routes = Parameters<typeof renderRouter>[0];

/**
 * Renders the given routes at `initialUrl` and resolves once they are on screen.
 *
 * `renderRouter` hangs its helpers on the promise it returns rather than on
 * what the promise resolves to, so they are read from the promise here.
 */
export async function openRouter(routes: Routes, initialUrl: string) {
  const rendering = renderRouter(routes, { initialUrl });
  await rendering;
  return {
    /** The path the router is on now, without query parameters. */
    pathname: (): string => rendering.getPathname(),
  };
}
