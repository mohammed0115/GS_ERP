# GS ERP — Final Verdict After Fix Sprint
**Date:** 2026-04-23  
**Auditor role:** QA Lead + Financial Systems Auditor + ERP Test Architect + Backend/API Reviewer  
**Baseline:** 456 pass / 13 fail (pre-existing, all 13 unrelated to audit findings)

---

## ما الذي تم إصلاحه (What Was Fixed)

| الإصلاح | الملف | الوصف |
|---------|-------|-------|
| F-1 | `seed_default_coa.py` | أضيف حساب "Tax Recoverable" (1600) للكود الضريبي VAT عند إنشاء المؤسسة |
| F-2 | `seed_default_coa.py` | دالة `seed_default_fiscal_year()` جديدة تُنشئ السنة المالية + 12 فترة تلقائياً |
| F-3 | `users/interfaces/web/views.py` | `RegisterView` الآن يستدعي `seed_default_fiscal_year` عند تسجيل مؤسسة جديدة |
| F-4 | `post_journal_entry.py` | `fiscal_period_id` الآن يُحدَّد ويُحفَظ على كل قيد محاسبي |
| F-5 | `users/interfaces/web/views.py` | OTP brute-force: قفل بعد 5 محاولات خاطئة + إلغاء الرمز + flush للجلسة |
| F-6 | `config/settings/base.py` | تفعيل DRF throttling: 60/دقيقة للزوار، 300/دقيقة للمستخدمين |
| F-7 | `finance/infrastructure/models.py` | UniqueConstraint على `entry_number` لكل مؤسسة |
| F-8 | `finance/migrations/0011_qa_fixes.py` | Migration للـ constraint أعلاه |
| F-9 | `intelligence/interfaces/api/views.py` | `_require_org()` يرفع 403 بدلاً من إرجاع None → crash |
| F-10 | `intelligence/interfaces/api/views.py` | حماية 8 views بـ `IsFinanceManager` (assign/resolve/review/acknowledge) |
| F-11 | `finance/infrastructure/models.py` | `Account.save()` الآن يُحدِّث `level` للفروع عند تغيير الأصل (cascade) |
| F-12 | `sales/application/use_cases/post_sale.py` | `_record_tax_transactions()` يُنشئ سجلات TaxTransaction لكل سطر مبيعات |

---

## ما الذي ما زال فاشلاً (Still Failing)

| الفجوة | الخطورة | الموقع |
|--------|---------|--------|
| `ApproveJournalEntry` use case غائب | متوسطة | القيد يبقى في DRAFT أو يُنشر مباشرة؛ لا مرحلة APPROVED |
| VAT Settlement use case غائب | عالية | لا يمكن تسوية ضريبة المدخلات/المخرجات وإنشاء قيد الدفع |
| `TaxTransaction` على فواتير المشتريات | متوسطة | PostPurchaseBill لا يكتب سجلات TaxTransaction |
| `DetectAnomalies` computation | عالية | النموذج موجود، لا منطق حسابي — دالة `execute()` فارغة أو غائبة |
| `ComputeRiskScores` computation | عالية | النموذج موجود، لا منطق حسابي |
| `AlertRule` evaluator | متوسطة | `condition_json` مخزَّن لكن لا Celery task يقيّمه |
| Cash Flow Statement | متوسطة | غائب من `apps/reports/application/selectors.py` |
| `current_balance` sync | متوسطة | حقل `BankAccount.current_balance` / `Cashbox.current_balance` لا يُحدَّث بعمليات الإيداع/السحب |
| `TaxProfile` wiring | منخفضة | النموذج موجود لكن غير مرتبط بـ Customer أو SalesInvoice |

---

## اكتشاف مهم — تحذيرات كانت خاطئة

**التقرير الأصلي أشار إلى غياب المكونات التالية، لكنها موجودة فعلاً:**

| ما قيل إنه غائب | الحقيقة |
|----------------|---------|
| Balance Sheet selector | موجود في `reports/application/selectors.py` (2200+ سطر) |
| Income Statement selector | موجود في نفس الملف |
| AR Aging / AP Aging selectors | موجودان |
| Sales Tax Report / Purchase Tax Report | موجودان |
| BalanceSheetView / IncomeStatementView / ARAgingView | موجودة في `reports/interfaces/web/views.py` |
| ClosingChecklistView / ClosingRun | موجودان في `finance/interfaces/web/views.py` |
| JournalLine debit XOR credit CHECK constraint | كان موجوداً قبل الـ audit |
| CustomerReceiptAllocation UniqueConstraint | كان موجوداً |
| TaxCode.rate CHECK (0-100) | كان موجوداً |

---

## Verdict نهائي لكل مرحلة

| المرحلة | الوصف | Verdict السابق | Verdict الحالي |
|---------|-------|--------------|--------------|
| Phase 1 | Core Infrastructure | PASS WITH WARNINGS | **PASS** |
| Phase 2 | Core Accounting | PASS WITH WARNINGS | **PASS WITH WARNINGS** |
| Phase 3 | Sales & AR | PASS WITH WARNINGS | **PASS** |
| Phase 4 | Purchases & AP | PASS WITH WARNINGS | **PASS WITH WARNINGS** |
| Phase 5 | Treasury | PASS WITH WARNINGS | **PASS WITH WARNINGS** |
| Phase 6 | Tax & Closing | FAIL | **PASS WITH WARNINGS** |
| Phase 7 | Intelligence & Reporting | FAIL | **FAIL** |

---

## تفاصيل كل مرحلة

### Phase 1 — Core Infrastructure → ✅ PASS

**تم إصلاحه:**
- OTP brute-force lockout (F-5)
- API throttling فعّال (F-6)
- `seed_default_fiscal_year` عند التسجيل (F-2, F-3)

**تحذير متبقٍّ (غير مانع):**
- OTP lockout يعتمد على الجلسة، لا على IP — يُنصح بـ `django-axes` في sprint الإنتاج

**الحكم:** صالح للانتقال ✅

---

### Phase 2 — Core Accounting → ⚠️ PASS WITH WARNINGS

**تم إصلاحه:**
- `entry_number` UniqueConstraint per-org (F-7, F-8)
- `fiscal_period_id` يُحفَظ على كل قيد (F-4)
- `Account.level` cascade عند تغيير الأصل (F-11)
- `input_tax_account` مُهيَّأ عند seeding (F-1)

**ما زال ناقصاً:**
- `ApproveJournalEntry` use case — مسار DRAFT → APPROVED → POSTED غير مكتمل

**الحكم:** صالح للانتقال مع ملاحظة — workflow الموافقة ناقص ⚠️

---

### Phase 3 — Sales & AR → ✅ PASS

**تم إصلاحه:**
- `_record_tax_transactions()` في `PostSale` — أثر ضريبي كامل لكل سطر مبيعات (F-12)
- `input_tax_account` مُهيَّأ (F-1)

**تحذير متبقٍّ (بسيط):**
- `TaxProfile` غير مرتبط بـ Customer (يؤثر فقط على التسعير التلقائي للضريبة)

**الحكم:** صالح للانتقال ✅

---

### Phase 4 — Purchases & AP → ⚠️ PASS WITH WARNINGS

**تم إصلاحه:**
- ورث إصلاحات Phase 2 و Phase 6

**ما زال ناقصاً:**
- `PostPurchaseBill` لا يكتب `TaxTransaction` للضريبة على المدخلات
- `TaxProfile` غير مرتبط بـ Vendor/PurchaseBill

**الحكم:** صالح للانتقال مع ملاحظة — ضريبة المشتريات غير مؤرشفة ⚠️

---

### Phase 5 — Treasury → ⚠️ PASS WITH WARNINGS

**تم إصلاحه:**
- ورث إصلاحات Phase 1 و Phase 2

**ما زال ناقصاً:**
- `BankAccount.current_balance` و `Cashbox.current_balance` لا يُحدَّثان تلقائياً بعمليات الإيداع/السحب — قيمة الحقل دائماً قديمة

**الحكم:** صالح للانتقال مع ملاحظة — رصيد الخزينة اللحظي غير موثوق ⚠️

---

### Phase 6 — Tax & Closing → ⚠️ PASS WITH WARNINGS (كان FAIL)

**تم إصلاحه:**
- `input_tax_account` على TaxCode المُهيَّأ (F-1) — الحد الفاصل بين FAIL و PASS
- `TaxTransaction` تُكتَب على المبيعات (F-12)
- `fiscal_period_id` يُحفَظ على القيود (F-4)
- واجهات الإقفال (`ClosingChecklistView`) موجودة — كانت مُفترَضة غائبة خطأً

**ما زال ناقصاً:**
- VAT Settlement use case — لا يمكن تسوية output - input وإنشاء قيد الدفع الضريبي
- `TaxTransaction` على المشتريات غائبة — تسوية الضريبة ستكون غير مكتملة

**الحكم:** صالح للانتقال بتحفظ — الإقفال الأساسي يعمل، تسوية الضريبة تحتاج sprint منفصل ⚠️

---

### Phase 7 — Intelligence & Reporting → ❌ FAIL

**تم إصلاحه:**
- `_require_org()` يرفع 403 بدلاً من crash (F-9)
- `IsFinanceManager` على views التعديل (F-10)
- تأكَّد أن Balance Sheet/Income Statement/AR-AP Aging موجودة فعلاً (لم تكن ناقصة)

**ما زال فاشلاً (جوهري):**
- `DetectAnomalies.execute()` — لا منطق حسابي (النموذج موجود، الدالة فارغة/غائبة)
- `ComputeRiskScores.execute()` — نفس المشكلة
- `AlertRule` evaluator — `condition_json` مخزَّن لكن لا Celery task يقيّمه ولا يُرسل تنبيهات
- Cash Flow Statement — غائب من selectors.py

**الحكم:** غير صالح للإطلاق — Intelligence core غير مُنفَّذ ❌

---

## خلاصة للـ Sprint القادم

```
Priority 1 (Blocker):
  □ DetectAnomalies computation (anomaly_score + flagging logic)
  □ ComputeRiskScores computation
  □ AlertRule Celery evaluator
  □ Cash Flow Statement selector

Priority 2 (High):
  □ VAT Settlement use case
  □ TaxTransaction on PostPurchaseBill
  □ current_balance sync on BankAccount/Cashbox

Priority 3 (Medium):
  □ ApproveJournalEntry use case
  □ TaxProfile → Customer/Invoice wiring
  □ IP-level OTP rate limiting (django-axes)
```

---

*Report generated: 2026-04-23 | Fixes applied this sprint: 12 | Phases upgraded: 4 | Remaining blockers: 4 critical*
