import { useForm } from "@tanstack/react-form";
import { useQuery } from "@tanstack/react-query";
import { fetchOrders, orderSchema } from "@/shared/api";
import { Button } from "@/shared/ui";

export function HomePage() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: fetchOrders });
  const form = useForm({
    defaultValues: { name: "", quantity: 1 },
    validators: { onChange: orderSchema },
    onSubmit: ({ value }) => {
      console.info(value.name);
    },
  });

  return (
    <main className="p-4">
      <p>{orders.data?.length ?? 0} orders</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void form.handleSubmit();
        }}
      >
        <form.Field name="name">
          {(field) => (
            <input
              value={field.state.value}
              onChange={(event) => {
                field.handleChange(event.target.value);
              }}
            />
          )}
        </form.Field>
        <Button type="submit">Save</Button>
      </form>
    </main>
  );
}
