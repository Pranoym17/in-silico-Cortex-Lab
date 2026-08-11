import type { Metadata } from "next";
import { PublicInformationPage } from "@/components/landing/PublicInformationPage";

export const metadata: Metadata = {
  title: "Terms of use | Cortex Lab",
  description: "Research-use terms for Cortex Lab."
};

export default function TermsPage() {
  return (
    <PublicInformationPage
      eyebrow="Terms of use"
      title="Build carefully. Share responsibly."
      introduction="Cortex Lab is a research-oriented workspace for constructing stimuli and inspecting simulated cortical-response output. By using it, you accept responsibility for your inputs, interpretation, and sharing decisions."
      sections={[
        {
          heading: "Your content",
          paragraphs: [
            "Only upload, process, and publish text, images, audio, video, and experimental materials that you are permitted to use. Preserve licenses, attribution, and source restrictions for all shared material.",
            "Do not submit protected health information, confidential information, unlawful content, or material that violates another person's rights."
          ]
        },
        {
          heading: "Research-only interpretation",
          paragraphs: [
            "Cortex Lab provides simulated model output. It is not medical advice, a diagnostic system, or a substitute for collected participant data, qualified research review, or expert analysis.",
            "You remain responsible for validating any research claim before relying on it or communicating it publicly."
          ]
        },
        {
          heading: "Public sharing",
          paragraphs: [
            "Published experiments, public URLs, and iframe embeds may be seen and forked by other people. Verify that a record is appropriate for public access before using the publish action.",
            "The platform may restrict content that creates a security, privacy, licensing, or research-integrity concern."
          ]
        }
      ]}
    />
  );
}
