'use client';

import { useEffect, useState } from 'react';

/** Returns true when viewport width is < 640px (Tailwind `sm` breakpoint). */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    function check() {
      setIsMobile(window.innerWidth < 640);
    }
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  return isMobile;
}
