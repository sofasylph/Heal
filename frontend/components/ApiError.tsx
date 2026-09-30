export function ApiError({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      Could not reach the ClaimTrace API ({message}). Start it with <code>make api</code> or{" "}
      <code>docker compose up</code>.
    </div>
  );
}
