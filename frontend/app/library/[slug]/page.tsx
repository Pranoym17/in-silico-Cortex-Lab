import { LibraryDetailClient } from "@/components/library/LibraryDetailClient";

export default function LibraryDetailPage({ params }: { params: { slug: string } }) {
  return <LibraryDetailClient slug={params.slug} />;
}
