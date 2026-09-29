import './globals.css';

export const metadata = {
  title: 'Scratly',
  description: 'Find a project that fits how you work',
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
