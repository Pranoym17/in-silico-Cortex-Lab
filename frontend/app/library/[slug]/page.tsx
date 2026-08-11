import { redirect } from "next/navigation";

export default function LibraryDetailPage({ params }: { params: { slug: string } }) {
  redirect(`/experiments/${params.slug}`);
}
