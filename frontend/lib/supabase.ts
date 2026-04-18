import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// Browser client (anon key, respects RLS)
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Server-side client: uses service role key to bypass RLS so API routes
// can query by user_id without Supabase auth context.
// Falls back to anon key if service role key not configured.
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
export const supabaseServer = createClient(
  supabaseUrl,
  serviceRoleKey ?? supabaseAnonKey,
  { auth: { persistSession: false, autoRefreshToken: false } }
);
