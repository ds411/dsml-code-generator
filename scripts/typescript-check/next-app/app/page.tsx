import { orderTable } from "@/shared/db";

export const dynamic = "force-dynamic";

export default function Page() {
  return <main>{orderTable._.name}</main>;
}
