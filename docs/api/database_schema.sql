-- =====================================================================
--  نظام ERP سحابي مماثل لدفترة - مخطط قاعدة البيانات الكامل
--  Database: PostgreSQL 16+
--  Strategy: Multi-Tenant (Shared Schema with Row-Level Security)
--  Encoding: UTF-8 (يدعم العربية بالكامل)
-- =====================================================================

-- إنشاء قاعدة البيانات
-- CREATE DATABASE daftra_clone WITH ENCODING 'UTF8' LC_COLLATE 'ar_SA.UTF-8';

-- تفعيل الإضافات المطلوبة
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- للبحث النصي السريع
CREATE EXTENSION IF NOT EXISTS "btree_gin";     -- للفهارس المركبة

-- =====================================================================
-- القسم 1: المستأجرون والمستخدمون والصلاحيات
-- =====================================================================

-- جدول المستأجرين (الشركات / المؤسسات المشتركة)
CREATE TABLE tenants (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(255) NOT NULL,
    name_ar             VARCHAR(255),
    subdomain           VARCHAR(100) UNIQUE NOT NULL,
    commercial_reg_no   VARCHAR(50),                -- السجل التجاري
    tax_number          VARCHAR(50),                -- الرقم الضريبي / VAT
    country_code        CHAR(2) NOT NULL DEFAULT 'SA',
    currency            CHAR(3) NOT NULL DEFAULT 'SAR',
    timezone            VARCHAR(50) DEFAULT 'Asia/Riyadh',
    locale              VARCHAR(10) DEFAULT 'ar',
    fiscal_year_start   INT DEFAULT 1,              -- شهر بدء السنة المالية
    plan                VARCHAR(20) NOT NULL DEFAULT 'trial',
                        -- trial | starter | professional | business | enterprise
    plan_expires_at     TIMESTAMPTZ,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
                        -- active | suspended | cancelled
    settings            JSONB DEFAULT '{}'::JSONB,
    logo_url            TEXT,
    address             JSONB,
    contact_phone       VARCHAR(30),
    contact_email       VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_subdomain ON tenants(subdomain);
CREATE INDEX idx_tenants_status    ON tenants(status);

-- جدول المستخدمين
CREATE TABLE users (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email               VARCHAR(255) NOT NULL,
    phone               VARCHAR(30),
    password_hash       TEXT NOT NULL,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100),
    full_name_ar        VARCHAR(200),
    avatar_url          TEXT,
    locale              VARCHAR(10) DEFAULT 'ar',
    timezone            VARCHAR(50) DEFAULT 'Asia/Riyadh',
    mfa_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret          TEXT,
    last_login_at       TIMESTAMPTZ,
    last_login_ip       INET,
    failed_attempts     INT NOT NULL DEFAULT 0,
    locked_until        TIMESTAMPTZ,
    email_verified_at   TIMESTAMPTZ,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_users_email_per_tenant UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant ON users(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email  ON users(email);

-- الأدوار والصلاحيات (RBAC)
CREATE TABLE roles (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE, -- NULL للأدوار النظامية
    name            VARCHAR(100) NOT NULL,
    name_ar         VARCHAR(100),
    description     TEXT,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE, -- أدوار افتراضية لا يمكن حذفها
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE permissions (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL, -- مثل: invoices.create, products.delete
    module          VARCHAR(50) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    name_ar         VARCHAR(100),
    description     TEXT
);

CREATE TABLE role_permissions (
    role_id         BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by     BIGINT REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);

-- جلسات المستخدمين (للـ Refresh Tokens)
CREATE TABLE user_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token   TEXT NOT NULL,
    user_agent      TEXT,
    ip_address      INET,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id) WHERE revoked_at IS NULL;

-- =====================================================================
-- القسم 2: العملاء والموردون
-- =====================================================================

CREATE TABLE customers (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_number     VARCHAR(50) NOT NULL,
    type                VARCHAR(20) NOT NULL DEFAULT 'individual', -- individual | business
    name                VARCHAR(255) NOT NULL,
    name_ar             VARCHAR(255),
    email               VARCHAR(255),
    phone               VARCHAR(30),
    mobile              VARCHAR(30),
    tax_number          VARCHAR(50),                -- VAT / TIN للأعمال
    commercial_reg_no   VARCHAR(50),
    nationality         VARCHAR(50),
    country_code        CHAR(2),
    city                VARCHAR(100),
    address_line1       TEXT,
    address_line2       TEXT,
    postal_code         VARCHAR(20),
    credit_limit        NUMERIC(18,4) DEFAULT 0,
    payment_terms_days  INT DEFAULT 0,             -- مهلة السداد
    price_list_id       BIGINT,
    notes               TEXT,
    custom_fields       JSONB DEFAULT '{}'::JSONB,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_customer_number_per_tenant UNIQUE (tenant_id, customer_number)
);

CREATE INDEX idx_customers_tenant   ON customers(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_name_trgm ON customers USING gin (name gin_trgm_ops);
CREATE INDEX idx_customers_phone    ON customers(tenant_id, phone);

-- الموردون (نفس بنية العملاء تقريباً)
CREATE TABLE suppliers (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    supplier_number     VARCHAR(50) NOT NULL,
    name                VARCHAR(255) NOT NULL,
    name_ar             VARCHAR(255),
    email               VARCHAR(255),
    phone               VARCHAR(30),
    tax_number          VARCHAR(50),
    address             TEXT,
    payment_terms_days  INT DEFAULT 30,
    custom_fields       JSONB DEFAULT '{}'::JSONB,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_supplier_number_per_tenant UNIQUE (tenant_id, supplier_number)
);

CREATE INDEX idx_suppliers_tenant ON suppliers(tenant_id) WHERE deleted_at IS NULL;

-- =====================================================================
-- القسم 3: المنتجات والمخزون
-- =====================================================================

CREATE TABLE product_categories (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id       BIGINT REFERENCES product_categories(id),
    name            VARCHAR(255) NOT NULL,
    name_ar         VARCHAR(255),
    sort_order      INT DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sku                 VARCHAR(100) NOT NULL,
    barcode             VARCHAR(100),
    name                VARCHAR(255) NOT NULL,
    name_ar             VARCHAR(255),
    description         TEXT,
    category_id         BIGINT REFERENCES product_categories(id),
    type                VARCHAR(20) NOT NULL DEFAULT 'product', -- product | service | digital
    unit                VARCHAR(20) DEFAULT 'piece',  -- قطعة، كرتون، كجم...
    cost_price          NUMERIC(18,4) DEFAULT 0,
    selling_price       NUMERIC(18,4) NOT NULL,
    tax_rate            NUMERIC(5,4) DEFAULT 0.15,    -- 15% VAT افتراضي
    track_inventory     BOOLEAN NOT NULL DEFAULT TRUE,
    reorder_point       NUMERIC(18,4) DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    image_url           TEXT,
    custom_fields       JSONB DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_product_sku_per_tenant UNIQUE (tenant_id, sku)
);

CREATE INDEX idx_products_tenant   ON products(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_barcode  ON products(tenant_id, barcode);
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- المستودعات
CREATE TABLE warehouses (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code            VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    name_ar         VARCHAR(255),
    address         TEXT,
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_warehouse_code_per_tenant UNIQUE (tenant_id, code)
);

-- أرصدة المخزون لكل منتج في كل مستودع
CREATE TABLE stock_balances (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    product_id      BIGINT NOT NULL REFERENCES products(id),
    warehouse_id    BIGINT NOT NULL REFERENCES warehouses(id),
    quantity        NUMERIC(18,4) NOT NULL DEFAULT 0,
    reserved_qty    NUMERIC(18,4) NOT NULL DEFAULT 0,
    available_qty   NUMERIC(18,4) GENERATED ALWAYS AS (quantity - reserved_qty) STORED,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_stock_per_warehouse UNIQUE (product_id, warehouse_id)
);

CREATE INDEX idx_stock_tenant_product ON stock_balances(tenant_id, product_id);

-- حركات المخزون (Audit Trail)
CREATE TABLE stock_movements (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    product_id      BIGINT NOT NULL REFERENCES products(id),
    warehouse_id    BIGINT NOT NULL REFERENCES warehouses(id),
    movement_type   VARCHAR(30) NOT NULL,
                    -- in_purchase | out_sale | adjustment_in | adjustment_out
                    -- transfer_in | transfer_out | return_in | return_out
    quantity        NUMERIC(18,4) NOT NULL,         -- موجبة أو سالبة
    unit_cost       NUMERIC(18,4),
    reference_type  VARCHAR(50),                    -- invoice | purchase_order | adjustment
    reference_id    BIGINT,
    notes           TEXT,
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_movements_product ON stock_movements(tenant_id, product_id, created_at DESC);
CREATE INDEX idx_movements_ref     ON stock_movements(tenant_id, reference_type, reference_id);

-- =====================================================================
-- القسم 4: الفواتير والمبيعات
-- =====================================================================

CREATE TABLE invoices (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invoice_number      VARCHAR(50) NOT NULL,
    invoice_type        VARCHAR(30) NOT NULL DEFAULT 'standard',
                        -- standard | simplified | credit_note | debit_note
    customer_id         BIGINT NOT NULL REFERENCES customers(id),
    issue_date          DATE NOT NULL,
    due_date            DATE,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft',
                        -- draft | sent | viewed | paid | partially_paid | overdue | cancelled
    currency            CHAR(3) NOT NULL DEFAULT 'SAR',
    exchange_rate       NUMERIC(12,6) DEFAULT 1.0,
    subtotal            NUMERIC(18,4) NOT NULL DEFAULT 0,
    discount_total      NUMERIC(18,4) NOT NULL DEFAULT 0,
    tax_total           NUMERIC(18,4) NOT NULL DEFAULT 0,
    shipping_total      NUMERIC(18,4) NOT NULL DEFAULT 0,
    total               NUMERIC(18,4) NOT NULL DEFAULT 0,
    paid_amount         NUMERIC(18,4) NOT NULL DEFAULT 0,
    balance_due         NUMERIC(18,4) GENERATED ALWAYS AS (total - paid_amount) STORED,

    -- ZATCA fields (Phase 2)
    uuid                UUID NOT NULL DEFAULT uuid_generate_v4(),
    invoice_hash        TEXT,
    previous_hash       TEXT,
    qr_code             TEXT,
    zatca_status        VARCHAR(20) DEFAULT 'pending',
                        -- pending | reported | cleared | rejected | not_required
    zatca_response      JSONB,
    zatca_cleared_xml   TEXT,
    zatca_submitted_at  TIMESTAMPTZ,

    notes               TEXT,
    terms               TEXT,
    custom_fields       JSONB DEFAULT '{}'::JSONB,
    sent_at             TIMESTAMPTZ,
    viewed_at           TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    created_by          BIGINT REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_invoice_per_tenant UNIQUE (tenant_id, invoice_number)
);

CREATE INDEX idx_invoices_tenant_date    ON invoices(tenant_id, issue_date DESC);
CREATE INDEX idx_invoices_customer       ON invoices(tenant_id, customer_id);
CREATE INDEX idx_invoices_status         ON invoices(tenant_id, status);
CREATE INDEX idx_invoices_zatca_status   ON invoices(tenant_id, zatca_status);

-- بنود الفاتورة
CREATE TABLE invoice_items (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    invoice_id      BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id      BIGINT REFERENCES products(id),
    description     VARCHAR(500) NOT NULL,
    quantity        NUMERIC(18,4) NOT NULL,
    unit_price      NUMERIC(18,4) NOT NULL,
    discount_pct    NUMERIC(5,4) DEFAULT 0,
    discount_amount NUMERIC(18,4) DEFAULT 0,
    tax_rate        NUMERIC(5,4) DEFAULT 0.15,
    tax_amount      NUMERIC(18,4) NOT NULL,
    line_total      NUMERIC(18,4) NOT NULL,
    line_order      INT NOT NULL,
    warehouse_id    BIGINT REFERENCES warehouses(id)
);

CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);

-- المدفوعات
CREATE TABLE payments (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    payment_number  VARCHAR(50) NOT NULL,
    payment_type    VARCHAR(20) NOT NULL,    -- received | sent
    customer_id     BIGINT REFERENCES customers(id),
    supplier_id     BIGINT REFERENCES suppliers(id),
    payment_date    DATE NOT NULL,
    method          VARCHAR(30) NOT NULL,    -- cash | card | bank_transfer | cheque | wallet
    amount          NUMERIC(18,4) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'SAR',
    bank_account_id BIGINT,
    reference       VARCHAR(100),            -- رقم العملية / الشيك
    notes           TEXT,
    status          VARCHAR(20) DEFAULT 'completed',
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payment_number_per_tenant UNIQUE (tenant_id, payment_number)
);

-- ربط المدفوعات بالفواتير (مدفوعة جزئياً، أو دفعة واحدة لعدة فواتير)
CREATE TABLE payment_allocations (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    payment_id      BIGINT NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    invoice_id      BIGINT NOT NULL REFERENCES invoices(id),
    amount          NUMERIC(18,4) NOT NULL
);

CREATE INDEX idx_payment_alloc_payment ON payment_allocations(payment_id);
CREATE INDEX idx_payment_alloc_invoice ON payment_allocations(invoice_id);

-- =====================================================================
-- القسم 5: المحاسبة (Chart of Accounts & Journal Entries)
-- =====================================================================

CREATE TABLE account_types (
    id          SMALLSERIAL PRIMARY KEY,
    code        VARCHAR(20) UNIQUE NOT NULL,
    name        VARCHAR(50) NOT NULL,
    name_ar     VARCHAR(50) NOT NULL,
    category    VARCHAR(20) NOT NULL,  -- asset | liability | equity | revenue | expense
    normal_balance VARCHAR(10) NOT NULL  -- debit | credit
);

INSERT INTO account_types (code, name, name_ar, category, normal_balance) VALUES
    ('CASH',        'Cash',                'النقدية',           'asset',     'debit'),
    ('AR',          'Accounts Receivable', 'الذمم المدينة',     'asset',     'debit'),
    ('INVENTORY',   'Inventory',           'المخزون',           'asset',     'debit'),
    ('FIXED_ASSET', 'Fixed Asset',         'الأصول الثابتة',    'asset',     'debit'),
    ('AP',          'Accounts Payable',    'الذمم الدائنة',     'liability', 'credit'),
    ('VAT_PAYABLE', 'VAT Payable',         'ضريبة القيمة المضافة', 'liability', 'credit'),
    ('EQUITY',      'Equity',              'حقوق الملكية',      'equity',    'credit'),
    ('REVENUE',     'Revenue',             'الإيرادات',         'revenue',   'credit'),
    ('COGS',        'Cost of Goods Sold',  'تكلفة البضاعة المباعة', 'expense',   'debit'),
    ('EXPENSE',     'Operating Expense',   'المصروفات',         'expense',   'debit');

-- دليل الحسابات (هرمي)
CREATE TABLE chart_of_accounts (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_code    VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    name_ar         VARCHAR(255),
    account_type_id SMALLINT NOT NULL REFERENCES account_types(id),
    parent_id       BIGINT REFERENCES chart_of_accounts(id),
    level           INT NOT NULL DEFAULT 1,
    is_group        BOOLEAN NOT NULL DEFAULT FALSE, -- حساب رئيسي أم فرعي
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_account_code_per_tenant UNIQUE (tenant_id, account_code)
);

CREATE INDEX idx_coa_tenant ON chart_of_accounts(tenant_id);
CREATE INDEX idx_coa_parent ON chart_of_accounts(parent_id);

-- مراكز التكلفة
CREATE TABLE cost_centers (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        VARCHAR(50) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    name_ar     VARCHAR(255),
    parent_id   BIGINT REFERENCES cost_centers(id),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_cc_code_per_tenant UNIQUE (tenant_id, code)
);

-- القيود اليومية (Journal Entries)
CREATE TABLE journal_entries (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entry_number    VARCHAR(50) NOT NULL,
    entry_date      DATE NOT NULL,
    description     TEXT,
    description_ar  TEXT,
    reference_type  VARCHAR(50),       -- invoice | payment | manual | adjustment
    reference_id    BIGINT,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft | posted | reversed
    fiscal_period   VARCHAR(7),        -- YYYY-MM
    is_locked       BOOLEAN NOT NULL DEFAULT FALSE,
    posted_at       TIMESTAMPTZ,
    posted_by       BIGINT REFERENCES users(id),
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_entry_number_per_tenant UNIQUE (tenant_id, entry_number)
);

CREATE INDEX idx_journal_tenant_date ON journal_entries(tenant_id, entry_date DESC);
CREATE INDEX idx_journal_period      ON journal_entries(tenant_id, fiscal_period);
CREATE INDEX idx_journal_ref         ON journal_entries(tenant_id, reference_type, reference_id);

-- بنود القيد (مدين/دائن)
CREATE TABLE journal_lines (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    journal_id      BIGINT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id      BIGINT NOT NULL REFERENCES chart_of_accounts(id),
    debit           NUMERIC(18,4) NOT NULL DEFAULT 0,
    credit          NUMERIC(18,4) NOT NULL DEFAULT 0,
    cost_center_id  BIGINT REFERENCES cost_centers(id),
    description     TEXT,
    line_order      INT NOT NULL,
    CONSTRAINT chk_debit_or_credit
        CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);

CREATE INDEX idx_journal_lines_journal ON journal_lines(journal_id);
CREATE INDEX idx_journal_lines_account ON journal_lines(account_id);

-- التحقق من توازن القيد (debit = credit)
CREATE OR REPLACE FUNCTION check_journal_balance()
RETURNS TRIGGER AS $$
DECLARE
    total_debit  NUMERIC;
    total_credit NUMERIC;
BEGIN
    IF NEW.status = 'posted' THEN
        SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
        INTO total_debit, total_credit
        FROM journal_lines
        WHERE journal_id = NEW.id;

        IF ABS(total_debit - total_credit) > 0.0001 THEN
            RAISE EXCEPTION 'Journal entry % not balanced: debit=% credit=%',
                            NEW.entry_number, total_debit, total_credit;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_journal_balance
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW
    WHEN (NEW.status = 'posted' AND OLD.status != 'posted')
    EXECUTE FUNCTION check_journal_balance();

-- =====================================================================
-- القسم 6: المشتريات
-- =====================================================================

CREATE TABLE purchase_orders (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    po_number       VARCHAR(50) NOT NULL,
    supplier_id     BIGINT NOT NULL REFERENCES suppliers(id),
    order_date      DATE NOT NULL,
    expected_date   DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                    -- draft | sent | partially_received | received | cancelled
    subtotal        NUMERIC(18,4) NOT NULL DEFAULT 0,
    tax_total       NUMERIC(18,4) NOT NULL DEFAULT 0,
    total           NUMERIC(18,4) NOT NULL DEFAULT 0,
    notes           TEXT,
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_po_number_per_tenant UNIQUE (tenant_id, po_number)
);

CREATE TABLE purchase_order_items (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    po_id           BIGINT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id      BIGINT NOT NULL REFERENCES products(id),
    quantity        NUMERIC(18,4) NOT NULL,
    received_qty    NUMERIC(18,4) NOT NULL DEFAULT 0,
    unit_cost       NUMERIC(18,4) NOT NULL,
    tax_rate        NUMERIC(5,4) DEFAULT 0.15,
    line_total      NUMERIC(18,4) NOT NULL,
    line_order      INT NOT NULL
);

-- =====================================================================
-- القسم 7: الموارد البشرية
-- =====================================================================

CREATE TABLE departments (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        VARCHAR(50) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    name_ar     VARCHAR(255),
    parent_id   BIGINT REFERENCES departments(id),
    manager_id  BIGINT,
    CONSTRAINT uq_dept_code_per_tenant UNIQUE (tenant_id, code)
);

CREATE TABLE employees (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    employee_number     VARCHAR(50) NOT NULL,
    user_id             BIGINT REFERENCES users(id),
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    full_name_ar        VARCHAR(200),
    national_id         VARCHAR(50),
    iqama_number        VARCHAR(50),
    nationality         VARCHAR(50),
    date_of_birth       DATE,
    gender              CHAR(1),
    marital_status      VARCHAR(20),
    email               VARCHAR(255),
    phone               VARCHAR(30),
    hire_date           DATE NOT NULL,
    end_date            DATE,
    department_id       BIGINT REFERENCES departments(id),
    job_title           VARCHAR(100),
    job_title_ar        VARCHAR(100),
    employment_type     VARCHAR(30),  -- full_time | part_time | contract
    basic_salary        NUMERIC(18,4) NOT NULL DEFAULT 0,
    bank_name           VARCHAR(100),
    bank_iban           VARCHAR(50),
    address             TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    custom_fields       JSONB DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_employee_number_per_tenant UNIQUE (tenant_id, employee_number)
);

CREATE INDEX idx_employees_tenant ON employees(tenant_id) WHERE is_active = TRUE;

-- البدلات والاستقطاعات
CREATE TABLE salary_components (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    employee_id     BIGINT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    component_type  VARCHAR(20) NOT NULL,  -- allowance | deduction
    name            VARCHAR(100) NOT NULL,
    amount          NUMERIC(18,4) NOT NULL,
    is_recurring    BOOLEAN NOT NULL DEFAULT TRUE,
    start_date      DATE,
    end_date        DATE
);

-- الحضور
CREATE TABLE attendance (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    employee_id     BIGINT NOT NULL REFERENCES employees(id),
    attendance_date DATE NOT NULL,
    check_in        TIMESTAMPTZ,
    check_out       TIMESTAMPTZ,
    work_hours      NUMERIC(5,2),
    overtime_hours  NUMERIC(5,2) DEFAULT 0,
    status          VARCHAR(20),  -- present | absent | late | on_leave | weekend | holiday
    notes           TEXT,
    CONSTRAINT uq_attendance_per_day UNIQUE (employee_id, attendance_date)
);

CREATE INDEX idx_attendance_emp_date ON attendance(employee_id, attendance_date DESC);

-- الإجازات
CREATE TABLE leave_requests (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    employee_id     BIGINT NOT NULL REFERENCES employees(id),
    leave_type      VARCHAR(30) NOT NULL,  -- annual | sick | unpaid | emergency
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    days_count      INT NOT NULL,
    reason          TEXT,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending | approved | rejected
    approved_by     BIGINT REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- مسيرات الرواتب
CREATE TABLE payroll_runs (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period_month    INT NOT NULL,
    period_year     INT NOT NULL,
    total_gross     NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_deductions NUMERIC(18,4) NOT NULL DEFAULT 0,
    total_net       NUMERIC(18,4) NOT NULL DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'draft',  -- draft | calculated | approved | paid
    approved_by     BIGINT REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payroll_period UNIQUE (tenant_id, period_year, period_month)
);

CREATE TABLE payslips (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    payroll_run_id  BIGINT NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id     BIGINT NOT NULL REFERENCES employees(id),
    basic_salary    NUMERIC(18,4) NOT NULL,
    allowances      NUMERIC(18,4) NOT NULL DEFAULT 0,
    overtime        NUMERIC(18,4) NOT NULL DEFAULT 0,
    deductions      NUMERIC(18,4) NOT NULL DEFAULT 0,
    gosi_employee   NUMERIC(18,4) NOT NULL DEFAULT 0,  -- التأمينات الاجتماعية
    gosi_employer   NUMERIC(18,4) NOT NULL DEFAULT 0,
    gross_salary    NUMERIC(18,4) NOT NULL,
    net_salary      NUMERIC(18,4) NOT NULL,
    details         JSONB,
    paid_at         TIMESTAMPTZ
);

-- =====================================================================
-- القسم 8: المشاريع
-- =====================================================================

CREATE TABLE projects (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code            VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    name_ar         VARCHAR(255),
    customer_id     BIGINT REFERENCES customers(id),
    manager_id      BIGINT REFERENCES employees(id),
    start_date      DATE,
    end_date        DATE,
    budget          NUMERIC(18,4),
    status          VARCHAR(20) DEFAULT 'planning',  -- planning | active | on_hold | completed | cancelled
    progress_pct    NUMERIC(5,2) DEFAULT 0,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_project_code_per_tenant UNIQUE (tenant_id, code)
);

CREATE TABLE tasks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    project_id      BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    parent_task_id  BIGINT REFERENCES tasks(id),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    assigned_to     BIGINT REFERENCES users(id),
    priority        VARCHAR(10) DEFAULT 'medium',  -- low | medium | high | urgent
    status          VARCHAR(20) DEFAULT 'todo',    -- todo | in_progress | review | done
    due_date        DATE,
    estimated_hours NUMERIC(5,2),
    actual_hours    NUMERIC(5,2) DEFAULT 0,
    sort_order      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE timesheets (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    project_id      BIGINT REFERENCES projects(id),
    task_id         BIGINT REFERENCES tasks(id),
    work_date       DATE NOT NULL,
    hours           NUMERIC(5,2) NOT NULL,
    description     TEXT,
    is_billable     BOOLEAN DEFAULT TRUE,
    hourly_rate     NUMERIC(18,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================================
-- القسم 9: سجل التدقيق (Audit Log)
-- =====================================================================

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    user_id         BIGINT REFERENCES users(id),
    action          VARCHAR(50) NOT NULL,        -- create | update | delete | login | export
    entity_type     VARCHAR(50) NOT NULL,        -- invoice | customer | product | ...
    entity_id       BIGINT,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- تقسيم الجدول شهرياً للأداء
CREATE TABLE audit_logs_2026_04 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE audit_logs_2026_05 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
-- ... أنشئ partition شهري عبر pg_cron

CREATE INDEX idx_audit_tenant_date ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_entity      ON audit_logs(tenant_id, entity_type, entity_id);

-- =====================================================================
-- القسم 10: Webhooks والتكامل
-- =====================================================================

CREATE TABLE webhooks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    events          TEXT[] NOT NULL,  -- ['invoice.created', 'payment.received', ...]
    secret          TEXT NOT NULL,    -- لتوقيع HMAC
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE webhook_deliveries (
    id              BIGSERIAL PRIMARY KEY,
    webhook_id      BIGINT NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type      VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    response_code   INT,
    response_body   TEXT,
    attempts        INT DEFAULT 0,
    delivered_at    TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE api_keys (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    key_hash        TEXT NOT NULL UNIQUE,
    key_prefix      VARCHAR(20) NOT NULL,
    scopes          TEXT[],
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================================
-- القسم 11: Row Level Security (عزل المستأجرين)
-- =====================================================================

-- تفعيل RLS على جميع جداول المستأجرين
ALTER TABLE customers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE products           ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices           ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items      ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments           ENABLE ROW LEVEL SECURITY;
ALTER TABLE chart_of_accounts  ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries    ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_lines      ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees          ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects           ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_balances     ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_movements    ENABLE ROW LEVEL SECURITY;

-- سياسة العزل: لا يمكن الوصول إلا لبيانات نفس المستأجر
CREATE POLICY tenant_isolation ON customers
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON suppliers
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON products
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON invoices
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON invoice_items
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON payments
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
CREATE POLICY tenant_isolation ON journal_entries
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);
-- ... كرر السياسة لباقي الجداول

-- =====================================================================
-- القسم 12: Functions & Triggers
-- =====================================================================

-- تحديث updated_at تلقائياً
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated  BEFORE UPDATE ON customers  FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_products_updated   BEFORE UPDATE ON products   FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_invoices_updated   BEFORE UPDATE ON invoices   FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_users_updated      BEFORE UPDATE ON users      FOR EACH ROW EXECUTE FUNCTION update_timestamp();
CREATE TRIGGER trg_tenants_updated    BEFORE UPDATE ON tenants    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- توليد رقم الفاتورة التلقائي
CREATE OR REPLACE FUNCTION generate_invoice_number(p_tenant_id UUID)
RETURNS VARCHAR AS $$
DECLARE
    v_year      INT := EXTRACT(YEAR FROM NOW());
    v_sequence  INT;
    v_number    VARCHAR;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(invoice_number FROM 'INV-\d+-(\d+)') AS INT)), 0) + 1
    INTO v_sequence
    FROM invoices
    WHERE tenant_id = p_tenant_id
      AND invoice_number LIKE 'INV-' || v_year || '-%';

    v_number := 'INV-' || v_year || '-' || LPAD(v_sequence::TEXT, 5, '0');
    RETURN v_number;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- نهاية المخطط
-- =====================================================================
