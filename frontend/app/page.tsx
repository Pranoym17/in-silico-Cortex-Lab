import type { Metadata } from "next";
import { CortexLandingPage } from "@/components/landing/CortexLandingPage";

export const metadata: Metadata = {
  title: "Cortex Lab | In-silico cortical research",
  description: "Design multimodal stimuli and inspect simulated cortical response on an interactive fsaverage5 surface."
};

export default function HomePage() {
  return <CortexLandingPage />;
}
