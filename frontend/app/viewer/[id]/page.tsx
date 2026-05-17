import { ResultsViewer } from "@/components/viewer/ResultsViewer";

export default function ViewerPage({ params }: { params: { id: string } }) {
  return <ResultsViewer experimentId={params.id} />;
}
