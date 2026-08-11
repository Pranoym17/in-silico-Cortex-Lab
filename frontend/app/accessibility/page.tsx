import type { Metadata } from "next";
import { PublicInformationPage } from "@/components/landing/PublicInformationPage";

export const metadata: Metadata = {
  title: "Accessibility | Cortex Lab",
  description: "Accessibility support and interface behavior in Cortex Lab."
};

export default function AccessibilityPage() {
  return (
    <PublicInformationPage
      eyebrow="Accessibility"
      title="Research tools should remain legible and operable."
      introduction="Cortex Lab is designed around keyboard-reachable controls, clear focus states, responsive layouts, and reduced-motion preferences. The product also provides a clear fallback when an interactive 3D surface is not available."
      sections={[
        {
          heading: "Interaction",
          paragraphs: [
            "Navigation, forms, timeline controls, buttons, and viewer controls are designed to be reachable by keyboard and to expose visible focus states.",
            "Controls use text, icons, and programmatic labels so their purpose is available beyond visual appearance alone."
          ]
        },
        {
          heading: "Motion and display",
          paragraphs: [
            "Cortex Lab respects reduced-motion preferences. Responsive layouts keep core workspace, builder, public record, and viewer actions available across desktop and mobile screen sizes.",
            "The cortical viewer requires WebGL for full interactivity. When WebGL is unavailable, the product displays a fallback rather than failing silently."
          ]
        },
        {
          heading: "Ongoing review",
          paragraphs: [
            "Accessibility needs vary by research workflow and assistive technology. Review real browser, keyboard, touch, and assistive-technology behavior before a public deployment, and treat reported barriers as product defects to resolve."
          ]
        }
      ]}
    />
  );
}
