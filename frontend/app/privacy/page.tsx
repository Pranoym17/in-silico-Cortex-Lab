import type { Metadata } from "next";
import { PublicInformationPage } from "@/components/landing/PublicInformationPage";

export const metadata: Metadata = {
  title: "Privacy | Cortex Lab",
  description: "Privacy and data-handling information for Cortex Lab research workspaces."
};

export default function PrivacyPage() {
  return (
    <PublicInformationPage
      eyebrow="Privacy and data"
      title="Research data should remain under deliberate control."
      introduction="Cortex Lab separates private research drafts from opt-in public sharing. This page explains the product-level data boundaries users should understand before creating or publishing an experiment."
      sections={[
        {
          heading: "Workspace data",
          paragraphs: [
            "A private workspace can contain account identity, experiment names, timeline blocks, uploaded stimuli, generated result artifacts, and processing metadata needed to run or inspect an experiment.",
            "Keep sensitive personal data, protected health information, confidential participant materials, and any data you are not authorized to process out of Cortex Lab."
          ]
        },
        {
          heading: "Authentication and services",
          paragraphs: [
            "Cortex Lab uses its configured authentication, storage, inference, queue, and observability services to provide sign-in, private drafts, uploads, processing, and results. Access is governed by the authenticated workspace and the deployment's service configuration.",
            "A deployment operator is responsible for configuring its approved cloud accounts, credentials, retention practices, and support contact before inviting public users."
          ]
        },
        {
          heading: "Public experiments",
          paragraphs: [
            "Publication is opt-in. A public experiment may make selected research metadata, public blocks, provenance, and read-only results available through its share URL or embed view.",
            "Review an experiment before publishing it, and remove content that should remain private before you make it available to others."
          ]
        }
      ]}
    />
  );
}
