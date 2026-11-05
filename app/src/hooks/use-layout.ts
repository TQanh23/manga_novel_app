import { useWindowDimensions } from 'react-native';

/** From this width the app is laid out for a desktop browser or a tablet held sideways. */
export const WIDE_BREAKPOINT = 1024;
const TWO_COLUMNS = 700;

/** How the screen is laid out at the window's current width. */
export function useLayout(): { isWide: boolean; columns: 1 | 2 | 3 } {
  const { width } = useWindowDimensions();
  const isWide = width >= WIDE_BREAKPOINT;
  return { isWide, columns: isWide ? 3 : width >= TWO_COLUMNS ? 2 : 1 };
}
