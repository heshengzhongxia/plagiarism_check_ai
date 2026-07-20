import type { ReactNode } from 'react';

interface MainLayoutProps {
  children: ReactNode;
}

function MainLayout({ children }: MainLayoutProps) {
  return (
    <main className="flex flex-1 min-h-0">
      {children}
    </main>
  );
}

export default MainLayout;
