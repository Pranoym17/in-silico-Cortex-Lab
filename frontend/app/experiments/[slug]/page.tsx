import { LibraryDetailClient } from "@/components/library/LibraryDetailClient";

export default function PublicExperimentPage({ params }: { params: { slug: string } }) {
  return <LibraryDetailClient slug={params.slug} />;
}
