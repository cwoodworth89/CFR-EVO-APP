// NOTE: For database schema, table layouts, and row-level security (RLS) policies, see docs/supabase_setup.md
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

let client = null;
try {
  if (supabaseUrl && supabaseAnonKey && !supabaseUrl.includes('your-project-ref')) {
    client = createClient(supabaseUrl, supabaseAnonKey);
  }
} catch (e) {
  console.warn('Supabase client initialization warning:', e);
}

export const supabase = client;
