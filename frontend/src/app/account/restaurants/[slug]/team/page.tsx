import TeamPageClient from "./TeamPageClient";

export function generateStaticParams() {
  return [{ slug: "__placeholder__" }];
}

export const dynamicParams = true;

export default function TeamPage() {
  return <TeamPageClient />;
}
