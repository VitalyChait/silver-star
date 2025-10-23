import './globals.css';

export const metadata = {
  title: "Silver Star",
  description: "Job board MVP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="container">
          <header className="header">
            <h1>Silver Star</h1>
            <p>Connecting senior professionals with meaningful work.</p>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
