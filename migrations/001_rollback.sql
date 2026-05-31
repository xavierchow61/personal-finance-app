-- ============================================================
-- Rollback for Migration 001 (RLS multi-user)
-- ============================================================
-- 用途：如果 RLS migration 之後 app 出問題想還原舊狀態
--
-- 注意：
-- - 呢個 script 會 DROP 新 public.* tables（含已遷移嘅 user_id 欄）
-- - 不會影響 user_xxx schema 嘅原始資料（仍然存在）
-- - app code 需要同時 revert 返用 search_path 模式
-- ============================================================

BEGIN;

-- 刪走新嘅 RLS-enabled tables
DROP TABLE IF EXISTS public.invoices CASCADE;
DROP TABLE IF EXISTS public.journal_lines CASCADE;
DROP TABLE IF EXISTS public.journal_entries CASCADE;
DROP TABLE IF EXISTS public.budgets CASCADE;
DROP TABLE IF EXISTS public.payment_aliases CASCADE;
DROP TABLE IF EXISTS public.fx_rates CASCADE;
DROP TABLE IF EXISTS public.credit_cards CASCADE;
DROP TABLE IF EXISTS public.loans CASCADE;
DROP TABLE IF EXISTS public.projects CASCADE;
DROP TABLE IF EXISTS public.accounts CASCADE;
DROP TABLE IF EXISTS public.closed_periods CASCADE;

COMMIT;

-- 之後 app code 仍會用 user_xxx schema（如果未 revert code）
-- 或者你可以重新跑 001_rls_multi_user.sql 重來
