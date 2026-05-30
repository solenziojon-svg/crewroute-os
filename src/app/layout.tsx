import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CrewRoute OS | CJS Landscape Solutions',
  description: 'The complete operating system for serious landscaping operators. AI-powered estimates, dispatch, photo audits, and business intelligence for CJS Landscape Solutions.',
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
      <body style={{ 
        margin: 0, 
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        backgroundColor: '#0a0a0a',
        color: '#e5e5e5'
      }}>
        {children}
      </body>
    </html>
  );
}