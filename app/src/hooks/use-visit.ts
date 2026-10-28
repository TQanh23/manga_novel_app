import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

/**
 * How many times the screen has come back into focus: 0 on the first visit,
 * then one more each time. Put it in a `useLoad` key to ask again on each return.
 */
export function useVisit(): number {
  const [visit, setVisit] = useState(0);
  const focusedBefore = useRef(false);
  useFocusEffect(
    useCallback(() => {
      if (focusedBefore.current) {
        setVisit((count) => count + 1);
      }
      focusedBefore.current = true;
    }, []),
  );
  return visit;
}
