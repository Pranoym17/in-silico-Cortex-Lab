import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cortex Lab | In-silico fMRI workspace",
  description: "Build multimodal research stimuli and inspect simulated cortical activation on fsaverage5."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

