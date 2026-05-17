import { ExperimentBuilder } from "@/components/builder/ExperimentBuilder";

export default function BuilderPage({ params }: { params: { id: string } }) {
  return <ExperimentBuilder experimentId={params.id} />;
}
