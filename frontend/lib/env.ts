function isClerkTestKey(value: string | undefined, prefix: "pk" | "sk") {
  if (!value) return false;
  return value.startsWith(`${prefix}_test_`);
}

export function assertVercelProductionClerkEnv() {
  if (process.env.VERCEL_ENV !== "production") return;

  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const secretKey = process.env.CLERK_SECRET_KEY;
  const issues: string[] = [];

  if (!publishableKey) {
    issues.push("Missing `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.");
  } else if (isClerkTestKey(publishableKey, "pk")) {
    issues.push(
      "`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is a Clerk development key (`pk_test_...`). Use the Clerk Production instance `pk_live_...` key in Vercel Production."
    );
  }

  if (!secretKey) {
    issues.push("Missing `CLERK_SECRET_KEY`.");
  } else if (isClerkTestKey(secretKey, "sk")) {
    issues.push(
      "`CLERK_SECRET_KEY` is a Clerk development key (`sk_test_...`). Use the Clerk Production instance `sk_live_...` key in Vercel Production."
    );
  }

  if (issues.length === 0) return;

  throw new Error(
    [
      "Invalid Clerk configuration for a Vercel production deployment.",
      ...issues,
      "Update the Vercel project environment variables, then redeploy.",
    ].join(" ")
  );
}
