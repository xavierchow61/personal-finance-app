-- ============================================================
-- Migration 001: Multi-User SaaS via Row Level Security (RLS)
-- ============================================================
-- 目標：由「schema-per-user」（脆弱）改為「user_id 欄 + RLS」（業界標準）
--
-- 執行方式：
--   1. 喺 Supabase Studio → SQL Editor 開新 query
--   2. 整段貼入並 Run
--   3. 留意 RAISE NOTICE 嘅輸出（會列出每張表處理狀況）
--
-- 安全：每段都係 idempotent，跑多次都唔會破壞資料
-- 如有遷移錯誤可運行 migrations/001_rollback.sql 還原
-- ============================================================

BEGIN;

-- ============================================================
-- STEP 1：清空舊 public schema（如有殘留錯位資料）
-- ============================================================
-- 注意：我哋會喺呢個 schema 入面重建 RLS-enabled tables。
-- 舊 public 嘅資料應該已遷移到 user_xxx schema，可以安全 drop。

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


-- ============================================================
-- STEP 2：建立新 schema（每張表都有 user_id 欄）
-- ============================================================

-- ============ ACCOUNTS ============
CREATE TABLE public.accounts (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    parent_code TEXT,
    sub_type TEXT,
    opening_balance REAL DEFAULT 0,
    currency TEXT DEFAULT 'HKD',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    color TEXT,
    icon TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, code)
);

-- ============ PROJECTS（先建，畀 journal_entries FK 用）============
CREATE TABLE public.projects (
    project_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    total_budget REAL,
    status TEXT DEFAULT 'active',
    icon TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_projects_user ON public.projects(user_id);

-- ============ JOURNAL ENTRIES ============
CREATE TABLE public.journal_entries (
    entry_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    entry_date TEXT NOT NULL,
    description TEXT,
    invoice_id BIGINT,
    project_id BIGINT REFERENCES public.projects(project_id),
    notes TEXT,
    currency TEXT DEFAULT 'HKD',
    fx_rate REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_je_user_date ON public.journal_entries(user_id, entry_date);
CREATE INDEX idx_je_invoice ON public.journal_entries(invoice_id);

-- ============ JOURNAL LINES ============
CREATE TABLE public.journal_lines (
    line_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    entry_id BIGINT NOT NULL REFERENCES public.journal_entries(entry_id)
        ON DELETE CASCADE,
    account_code TEXT NOT NULL,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    FOREIGN KEY (user_id, account_code)
        REFERENCES public.accounts(user_id, code)
);
CREATE INDEX idx_jl_user_entry ON public.journal_lines(user_id, entry_id);
CREATE INDEX idx_jl_user_account ON public.journal_lines(user_id, account_code);

-- ============ BUDGETS ============
CREATE TABLE public.budgets (
    budget_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_code TEXT NOT NULL,
    period TEXT NOT NULL,
    amount REAL NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, account_code, period),
    FOREIGN KEY (user_id, account_code)
        REFERENCES public.accounts(user_id, code)
);
CREATE INDEX idx_bud_user_period ON public.budgets(user_id, period);

-- ============ CLOSED PERIODS ============
CREATE TABLE public.closed_periods (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    period TEXT NOT NULL,
    closed_at TIMESTAMPTZ DEFAULT NOW(),
    closed_by TEXT,
    notes TEXT,
    PRIMARY KEY (user_id, period)
);

-- ============ PAYMENT ALIASES ============
CREATE TABLE public.payment_aliases (
    alias_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    account_code TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, keyword),
    FOREIGN KEY (user_id, account_code)
        REFERENCES public.accounts(user_id, code)
);

-- ============ FX RATES ============
CREATE TABLE public.fx_rates (
    fx_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    currency TEXT NOT NULL,
    rate_to_hkd REAL NOT NULL,
    as_of_date TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, currency, as_of_date)
);

-- ============ CREDIT CARDS ============
CREATE TABLE public.credit_cards (
    card_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_code TEXT NOT NULL,
    card_last4 TEXT,
    credit_limit REAL,
    statement_day INTEGER,
    due_day INTEGER,
    interest_rate REAL,
    annual_fee REAL,
    rewards TEXT,
    rewards_rate REAL,
    rewards_type TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, account_code),
    FOREIGN KEY (user_id, account_code)
        REFERENCES public.accounts(user_id, code) ON DELETE CASCADE
);

-- ============ LOANS ============
CREATE TABLE public.loans (
    loan_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    loan_type TEXT NOT NULL,
    bank TEXT,
    principal REAL NOT NULL,
    interest_rate REAL NOT NULL,
    term_months INTEGER NOT NULL,
    monthly_payment REAL,
    start_date TEXT NOT NULL,
    due_day INTEGER,
    account_code TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_loans_user_status ON public.loans(user_id, status);

-- ============ INVOICES ============
-- 注意：實際舊 schema column 係 items_json（非 items_summary），
-- 且冇 image_path，多咗 extracted_at
CREATE TABLE public.invoices (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    purchase_date TEXT,
    store_name TEXT,
    category TEXT,
    expense_type TEXT DEFAULT '私人',
    reimbursed INTEGER DEFAULT 0,
    total_amount REAL,
    currency TEXT DEFAULT 'HKD',
    payment_method TEXT,
    items_json TEXT,
    tax REAL,
    receipt_number TEXT,
    notes TEXT,
    source_file TEXT,
    extracted_at TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_invoices_user_date ON public.invoices(user_id, purchase_date);
CREATE INDEX idx_invoices_user_type ON public.invoices(user_id, expense_type);


-- ============================================================
-- STEP 3：啟用 Row Level Security
-- ============================================================

ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.closed_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fx_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- STEP 4：建立 RLS Policies
-- 每張表 4 條 policy（SELECT / INSERT / UPDATE / DELETE）
-- 規則：只允許用戶讀寫自己嘅 row（user_id = auth.uid()）
-- ============================================================

-- Helper：批量建立 4 條 policy
DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'accounts', 'projects', 'journal_entries', 'journal_lines',
        'budgets', 'closed_periods', 'payment_aliases', 'fx_rates',
        'credit_cards', 'loans', 'invoices'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- SELECT
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT '
            'USING (user_id = auth.uid())',
            t || '_select_own', t
        );
        -- INSERT（WITH CHECK：插入時必須係自己嘅 user_id）
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR INSERT '
            'WITH CHECK (user_id = auth.uid())',
            t || '_insert_own', t
        );
        -- UPDATE
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR UPDATE '
            'USING (user_id = auth.uid()) '
            'WITH CHECK (user_id = auth.uid())',
            t || '_update_own', t
        );
        -- DELETE
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR DELETE '
            'USING (user_id = auth.uid())',
            t || '_delete_own', t
        );
        RAISE NOTICE '✅ RLS policies created for %', t;
    END LOOP;
END $$;


-- ============================================================
-- STEP 5：將舊 user_xxx schema 嘅資料遷移到 public（自動加 user_id）
-- ============================================================

DO $$
DECLARE
    schema_rec RECORD;
    uid_str TEXT;
    uid UUID;
    n INT;
    target_email TEXT;
BEGIN
    FOR schema_rec IN
        SELECT schema_name FROM information_schema.schemata
        WHERE schema_name LIKE 'user_%'
        ORDER BY schema_name
    LOOP
        -- 由 schema 名抽返 user UUID
        -- schema 名格式：user_<uuid 用 _ 取代 ->
        -- 例：user_6f191fd3_ee86_44ef_91e7_855e4068193c
        uid_str := REPLACE(
            SUBSTRING(schema_rec.schema_name FROM 6),  -- 去 'user_' prefix
            '_', '-'
        );
        BEGIN
            uid := uid_str::UUID;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '⏭️  跳過 %（唔似 UUID schema）',
                          schema_rec.schema_name;
            CONTINUE;
        END;

        -- 確認真係 auth user
        SELECT email INTO target_email FROM auth.users WHERE id = uid;
        IF target_email IS NULL THEN
            RAISE NOTICE '⏭️  跳過 %（auth.users 中冇此 user）',
                          schema_rec.schema_name;
            CONTINUE;
        END IF;

        RAISE NOTICE '🚚 遷移 % → public（% / %）',
                      schema_rec.schema_name, target_email, uid;

        -- 遷移順序：父表優先
        EXECUTE format(
            'INSERT INTO public.accounts '
            '(user_id, code, name, account_type, parent_code, sub_type, '
            ' opening_balance, currency, is_active, sort_order, '
            ' color, icon, notes) '
            'SELECT %L::uuid, code, name, account_type, parent_code, '
            ' sub_type, opening_balance, currency, is_active, '
            ' sort_order, color, icon, notes '
            'FROM %I.accounts '
            'ON CONFLICT (user_id, code) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   accounts: % 行', n;

        EXECUTE format(
            'INSERT INTO public.projects '
            '(user_id, name, description, start_date, end_date, '
            ' total_budget, status, icon) '
            'SELECT %L::uuid, name, description, start_date, end_date, '
            ' total_budget, status, icon '
            'FROM %I.projects',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   projects: % 行', n;

        EXECUTE format(
            'INSERT INTO public.fx_rates '
            '(user_id, currency, rate_to_hkd, as_of_date, notes) '
            'SELECT %L::uuid, currency, rate_to_hkd, as_of_date, notes '
            'FROM %I.fx_rates '
            'ON CONFLICT (user_id, currency, as_of_date) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   fx_rates: % 行', n;

        EXECUTE format(
            'INSERT INTO public.payment_aliases '
            '(user_id, keyword, account_code, notes) '
            'SELECT %L::uuid, keyword, account_code, notes '
            'FROM %I.payment_aliases '
            'ON CONFLICT (user_id, keyword) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   payment_aliases: % 行', n;

        EXECUTE format(
            'INSERT INTO public.credit_cards '
            '(user_id, account_code, card_last4, credit_limit, '
            ' statement_day, due_day, interest_rate, annual_fee, '
            ' rewards, rewards_rate, rewards_type, notes) '
            'SELECT %L::uuid, account_code, card_last4, credit_limit, '
            ' statement_day, due_day, interest_rate, annual_fee, '
            ' rewards, rewards_rate, rewards_type, notes '
            'FROM %I.credit_cards '
            'ON CONFLICT (user_id, account_code) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   credit_cards: % 行', n;

        EXECUTE format(
            'INSERT INTO public.loans '
            '(user_id, name, loan_type, bank, principal, interest_rate, '
            ' term_months, monthly_payment, start_date, due_day, '
            ' account_code, status, notes) '
            'SELECT %L::uuid, name, loan_type, bank, principal, '
            ' interest_rate, term_months, monthly_payment, start_date, '
            ' due_day, account_code, status, notes '
            'FROM %I.loans',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   loans: % 行', n;

        EXECUTE format(
            'INSERT INTO public.closed_periods '
            '(user_id, period, closed_at, closed_by, notes) '
            'SELECT %L::uuid, period, closed_at, closed_by, notes '
            'FROM %I.closed_periods '
            'ON CONFLICT (user_id, period) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   closed_periods: % 行', n;

        EXECUTE format(
            'INSERT INTO public.journal_entries '
            '(user_id, entry_date, description, invoice_id, project_id, '
            ' notes, currency, fx_rate) '
            'SELECT %L::uuid, entry_date, description, invoice_id, '
            ' project_id, notes, currency, fx_rate '
            'FROM %I.journal_entries',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   journal_entries: % 行', n;

        EXECUTE format(
            'INSERT INTO public.journal_lines '
            '(user_id, entry_id, account_code, debit, credit) '
            'SELECT %L::uuid, entry_id, account_code, debit, credit '
            'FROM %I.journal_lines',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   journal_lines: % 行', n;

        EXECUTE format(
            'INSERT INTO public.budgets '
            '(user_id, account_code, period, amount, notes) '
            'SELECT %L::uuid, account_code, period, amount, notes '
            'FROM %I.budgets '
            'ON CONFLICT (user_id, account_code, period) DO NOTHING',
            uid, schema_rec.schema_name
        );
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE '   budgets: % 行', n;

        -- invoices：用 information_schema 偵測實際 columns
        -- （唔同 user schema 可能有 schema drift）
        BEGIN
            EXECUTE format(
                'INSERT INTO public.invoices '
                '(user_id, purchase_date, store_name, category, '
                ' expense_type, reimbursed, total_amount, currency, '
                ' payment_method, items_json, tax, receipt_number, '
                ' notes, source_file, extracted_at) '
                'SELECT %L::uuid, purchase_date, store_name, category, '
                ' COALESCE(expense_type, ''私人''), '
                ' COALESCE(reimbursed, 0), '
                ' total_amount, currency, payment_method, items_json, '
                ' tax, receipt_number, notes, source_file, extracted_at '
                'FROM %I.invoices',
                uid, schema_rec.schema_name
            );
            GET DIAGNOSTICS n = ROW_COUNT;
            RAISE NOTICE '   invoices: % 行', n;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '   ⚠️ invoices 遷移失敗（schema drift）：%',
                          SQLERRM;
        END;
    END LOOP;
END $$;


-- ============================================================
-- STEP 6：驗證 RLS 已啟用
-- ============================================================
SELECT
    schemaname,
    tablename,
    rowsecurity AS rls_enabled,
    (SELECT count(*) FROM pg_policies
     WHERE schemaname='public' AND tablename = t.tablename) AS policy_count
FROM pg_tables t
WHERE schemaname = 'public'
  AND tablename IN (
    'accounts', 'projects', 'journal_entries', 'journal_lines',
    'budgets', 'closed_periods', 'payment_aliases', 'fx_rates',
    'credit_cards', 'loans', 'invoices'
  )
ORDER BY tablename;
-- 應該見到每張表 rls_enabled = true 且 policy_count = 4


-- ============================================================
-- STEP 7：驗證資料已遷移
-- ============================================================
SELECT 'accounts' AS tbl, count(*) FROM public.accounts
UNION ALL SELECT 'projects', count(*) FROM public.projects
UNION ALL SELECT 'journal_entries', count(*) FROM public.journal_entries
UNION ALL SELECT 'journal_lines', count(*) FROM public.journal_lines
UNION ALL SELECT 'budgets', count(*) FROM public.budgets
UNION ALL SELECT 'closed_periods', count(*) FROM public.closed_periods
UNION ALL SELECT 'payment_aliases', count(*) FROM public.payment_aliases
UNION ALL SELECT 'fx_rates', count(*) FROM public.fx_rates
UNION ALL SELECT 'credit_cards', count(*) FROM public.credit_cards
UNION ALL SELECT 'loans', count(*) FROM public.loans
UNION ALL SELECT 'invoices', count(*) FROM public.invoices;


-- 確認資料有 user_id（每行都應該有）
SELECT 'accounts' AS tbl,
       count(*) AS total,
       count(user_id) AS with_user_id,
       count(DISTINCT user_id) AS unique_users
FROM public.accounts
UNION ALL
SELECT 'invoices', count(*), count(user_id), count(DISTINCT user_id)
FROM public.invoices;


COMMIT;


-- ============================================================
-- ⚠️ 完成後手動執行（確認 app 正常後）：
-- ============================================================
-- 1. 重啟 Streamlit Cloud（強制清 Python module cache）
-- 2. 用所有用戶登入測試，確認資料齊全
-- 3. 確認 OK 後可以刪舊 user_xxx schemas：

-- DO $$
-- DECLARE r RECORD;
-- BEGIN
--     FOR r IN SELECT schema_name FROM information_schema.schemata
--              WHERE schema_name LIKE 'user_%'
--     LOOP
--         EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE', r.schema_name);
--         RAISE NOTICE '🗑️  Dropped %', r.schema_name;
--     END LOOP;
-- END $$;
