// src/app/layout.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CrewRoute OS',
  description: 'Mobile Field Tool - Estimate & Audit',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body 
        style={{ 
          margin: 0, 
          padding: 0, 
          background: '#0A0C14',
          color: '#E8ECF1',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}
      >
        {children}
      </body>
    </html>
  );
}