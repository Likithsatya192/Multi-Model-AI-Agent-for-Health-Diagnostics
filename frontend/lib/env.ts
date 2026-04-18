function isClerkTestKey(value: string | undefined, prefix: "pk" | "sk") {
  if (!value) return false;
  return value.startsWith(`${prefix}_test_`);
}

export function assertVercelProductionClerkEnv() {
  if (process.env.VERCEL_ENV !== "production") return;

  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const secretKey = process.env.CLERK_SECRET_KEY;

  if (!publishableKey) {
    throw new Error("Missing `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` in Vercel production.");
  }

  if (!secretKey) {
    throw new Error("Missing `CLERK_SECRET_KEY` in Vercel production.");
  }
}
