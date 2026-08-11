import { PublicResultsViewer } from "@/components/viewer/PublicResultsViewer";

export default function EmbedExperimentPage({ params }: { params: { slug: string } }) {
  return <main className="embed-page"><PublicResultsViewer slug={params.slug} /></main>;
}
