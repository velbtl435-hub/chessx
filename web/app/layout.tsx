export const metadata = { title: "ChessX web", description: "Agentic meta-search on a board of squares" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
