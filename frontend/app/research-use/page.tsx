import type { Metadata } from "next";
import { PublicInformationPage } from "@/components/landing/PublicInformationPage";

export const metadata: Metadata = {
  title: "Research use | Cortex Lab",
  description: "How to interpret Cortex Lab's in-silico cortical research outputs."
};

export default function ResearchUsePage() {
  return (
    <PublicInformationPage
      eyebrow="Research-use statement"
      title="Use the signal with its limitations intact."
      introduction="Cortex Lab is designed to support transparent stimulus experiments and simulated cortical-response exploration. It is not a clinical, diagnostic, or participant-measurement system."
      sections={[
        {
          heading: "What the viewer represents",
          paragraphs: [
            "Cortical surfaces and activation timelines represent model-generated, average-subject predictions. They do not represent a scan, a diagnosis, or an observation about an individual person.",
            "Interpret results alongside the recorded stimulus, timing, model version, processing settings, and known limitations of the inference method."
          ]
        },
        {
          heading: "Appropriate use",
          paragraphs: [
            "Use Cortex Lab for exploratory research design, educational demonstrations, method prototyping, and transparent comparison of modeled responses.",
            "Do not use outputs to make medical, clinical, safety-critical, or individual-level decisions."
          ]
        },
        {
          heading: "Responsible sharing",
          paragraphs: [
            "Experiments begin as private drafts. Publishing and forking are deliberate actions, so review visible blocks, media, result metadata, and attribution before sharing a public record.",
            "Only upload and publish material you are authorized to use, and preserve any required licensing or attribution information."
          ]
        }
      ]}
    />
  );
}
