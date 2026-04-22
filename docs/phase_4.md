Phase 4 — الخزينة، الصندوق، البنوك، والتحويلات

Cash, Bank & Treasury Management

هذه المرحلة مهمة جدًا لأنها تربط:

التحصيل
المدفوعات
النقدية
الأرصدة البنكية
السيولة
التسويات

بعدها يصبح عندك نظام محاسبي أكثر واقعية وقابلًا للاستخدام اليومي داخل الشركات.

1. اسم المرحلة

Phase 4: Treasury, Cashboxes, Bank Accounts & Reconciliation

2. الهدف من المرحلة

بناء طبقة الخزينة التي تدير حركة الأموال الفعلية داخل النظام، سواء كانت:

نقدًا
عبر البنك
تحويلات داخلية
تحصيلات العملاء
مدفوعات الموردين
تسويات بنكية

في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:

إنشاء خزائن وصناديق
إنشاء حسابات بنكية
تسجيل الحركات النقدية والبنكية
تسجيل التحويل بين صندوق وبنك أو بين حسابين
ربط التحصيلات والمدفوعات بوسائل الدفع
متابعة الرصيد اللحظي
تنفيذ التسوية البنكية
منع العجز أو الحركات غير المنطقية حسب السياسة
إنتاج تقارير حركة النقد والبنك
3. لماذا هذه المرحلة مهمة؟

لأن المبيعات والمشتريات وحدها لا تكفي.
الأسئلة الحقيقية في أي شركة تكون مثل:

كم الرصيد في البنك الآن؟
كم الموجود في الصندوق؟
هل التحصيل دخل فعلًا؟
هل الدفعة خرجت فعلًا؟
ما الفرق بين رصيد النظام وكشف البنك؟
هل يوجد شيكات معلقة أو حوالات غير مسواة؟

وهذه كلها لا تُحل إلا بمرحلة Treasury.

4. حدود المرحلة
داخل النطاق
الصناديق Cashboxes
الحسابات البنكية Bank Accounts
وسائل الدفع
سندات القبض والصرف المرتبطة بالخزينة
التحويلات الداخلية
الحركة النقدية
الحركة البنكية
الأرصدة الجارية
التسوية البنكية
كشف حركة الصندوق
كشف حركة البنك
تقارير السيولة الأساسية
خارج النطاق
التمويل والاستثمارات
التسهيلات البنكية المعقدة
خطابات الضمان
الاعتمادات المستندية
إدارة الشيكات المؤجلة المتقدمة
التنبؤ النقدي الذكي
التكامل البنكي المباشر
إدارة المحافظ الاستثمارية
5. المخرجات النهائية المطلوبة من Phase 4

في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:

إنشاء صندوق أو أكثر
إنشاء حساب بنكي أو أكثر
ربط كل صندوق/بنك بحساب محاسبي صحيح
تسجيل حركة إيداع نقدي
تسجيل حركة سحب نقدي
تسجيل دفع من بنك أو صندوق
تسجيل تحصيل إلى بنك أو صندوق
تنفيذ تحويل داخلي بين:
صندوق وصندوق
بنك وبنك
صندوق وبنك
بنك وصندوق
احتساب الرصيد الحالي لكل صندوق وحساب بنكي
تنفيذ تسوية بنكية
عرض الحركات غير المسواة
استخراج كشف حساب الصندوق
استخراج كشف حساب البنك
استخراج ملخص السيولة
6. الموديولات التنفيذية داخل Phase 4
6.1 Module A — Cashboxes

هذا الموديول يدير الصناديق النقدية.

المطلوب
إنشاء صندوق
تعديل بياناته
تفعيله/تعطيله
ربطه بحساب محاسبي
عرض رصيده الحالي
التحكم في مستخدميه إن لزم
الكيان
Cashbox
الحقول الأساسية
id
organization_id
branch_id
code
name
currency
gl_account_id
opening_balance
current_balance
status
created_at
updated_at
قواعد الأعمال
كل صندوق يتبع شركة وفرعًا
كل صندوق يجب أن يرتبط بحساب أستاذ عام
لا يجوز حذف صندوق عليه حركات
يمكن تعطيله بدل حذفه
يمكن منع الرصيد السالب حسب السياسة
6.2 Module B — Bank Accounts

هذا الموديول يدير الحسابات البنكية.

المطلوب
إنشاء حساب بنكي
ربطه بالحساب المحاسبي
تخزين بيانات البنك
عرض رصيده النظامي
إدارة حالته
الكيان
BankAccount
الحقول الأساسية
id
organization_id
branch_id
bank_name
account_name
account_number
iban
swift_code
currency
gl_account_id
opening_balance
current_balance
status
created_at
updated_at
قواعد الأعمال
كل حساب بنكي يجب أن يرتبط بحساب أستاذ
لا يجوز حذف حساب بنكي عليه حركات
يمكن تعطيله بدل الحذف
يجب أن تكون العملة متوافقة مع الحركات المسجلة عليه
6.3 Module C — Payment Methods

هذا موديول تنظيمي يربط بين العمليات ووسيلة السداد.

المطلوب

تعريف وسائل مثل:

Cash
Bank Transfer
Check
Card
Online Payment
Internal Transfer
الكيان
PaymentMethod
الحقول الأساسية
id
code
name
type
is_active
قواعد الأعمال
كل تحصيل أو دفع يجب أن يحدد وسيلة دفع
بعض الوسائل تتطلب مرجعًا مثل رقم التحويل أو الشيك
6.4 Module D — Treasury Transactions

هذا هو قلب المرحلة.

المطلوب
تسجيل الحركة المالية الفعلية
نوع الحركة:
Inflow
Outflow
Transfer
Adjustment
ربط الحركة بمصدرها:
Receipt
Vendor Payment
Manual Treasury Entry
Transfer
Opening Balance
الكيان
TreasuryTransaction
الحقول الأساسية
id
organization_id
branch_id
transaction_number
transaction_date
transaction_type
treasury_source_type
treasury_source_id
payment_method_id
cashbox_id
bank_account_id
amount
currency
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
قواعد الأعمال
الحركة يجب أن ترتبط بوجهة مالية واضحة: صندوق أو بنك
لا يمكن أن تكون الحركة بلا حساب مالي فعلي
لا يجوز ترحيل الحركة في فترة مغلقة
لا يجوز تعديل الحركة بعد ترحيلها
يجب أن تنتج أثرًا محاسبيًا واضحًا
6.5 Module E — Cash In / Cash Out

هذا الموديول مخصص للحركات المباشرة على الصندوق.

المطلوب
سند قبض نقدي مباشر
سند صرف نقدي مباشر
ربط الحركة بسبب واضح
تحديث رصيد الصندوق
القيد المحاسبي الشائع

في حالة قبض نقدي:
مدين: الصندوق
دائن: الحساب المقابل

في حالة صرف نقدي:
مدين: الحساب المقابل
دائن: الصندوق

قواعد الأعمال
لا يجوز الصرف من صندوق غير نشط
لا يجوز الصرف بقيمة سالبة
يمكن فرض منع الرصيد السالب
كل حركة يجب أن يكون لها سبب ومرجع
6.6 Module F — Bank In / Bank Out

هذا الموديول للحركات المباشرة على الحساب البنكي.

المطلوب
إيداع بنكي
سحب بنكي
قيد رسوم بنكية
قيد فائدة أو أي حركة نظامية
تحديث الرصيد النظامي للحساب البنكي
القيد المحاسبي الشائع

في حالة إيداع:
مدين: البنك
دائن: الحساب المقابل

في حالة سحب:
مدين: الحساب المقابل
دائن: البنك

قواعد الأعمال
لا يجوز الحركة على حساب بنكي غير نشط
المرجع البنكي مطلوب في حالات التحويل والسحب
لا يجوز الترحيل في فترة مغلقة
يجب تتبع مصدر الحركة
6.7 Module G — Internal Transfers

هذا موديول مهم جدًا في العمليات اليومية.

المطلوب

دعم التحويل بين:

صندوق إلى صندوق
بنك إلى بنك
صندوق إلى بنك
بنك إلى صندوق
الكيان
TreasuryTransfer
الحقول الأساسية
id
organization_id
branch_id
transfer_number
transfer_date
from_cashbox_id
from_bank_account_id
to_cashbox_id
to_bank_account_id
amount
currency
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
القيد المحاسبي الشائع

مدين: الحساب المستقبل
دائن: الحساب المُحوِّل

قواعد الأعمال
يجب أن يكون هناك مصدر ووجهة
لا يجوز أن يكون المصدر والوجهة نفس الحساب
لا يجوز التحويل بمبلغ صفري أو سالب
لا يجوز التحويل في فترة مغلقة
يجب أن يظهر الأثر على الرصيدين معًا
6.8 Module H — Treasury Posting Engine

هذا الموديول يربط حركات الخزينة بالنواة المحاسبية.

المطلوب
ترحيل الحركة
إنشاء القيد المحاسبي
ربطه بالحركة
تحديث حالة الحركة
تحديث الأرصدة النظامية
الخدمات الأساسية
PostTreasuryTransactionService
PostTreasuryTransferService
التحقق
الحركة موجودة
الحالة Draft
الحسابات المالية معرفة
الفترة مفتوحة
المبلغ صحيح
لا يوجد تكرار ترحيل
المخرجات
إنشاء JournalEntry
تغيير الحالة إلى Posted
تحديث current_balance
تسجيل Audit Log
6.9 Module I — Bank Reconciliation

هذا من أهم أجزاء المرحلة.

المطلوب
إدخال أو استيراد كشف بنكي
مطابقة الحركات البنكية مع النظام
تعليم الحركات كمسواة أو غير مسواة
إظهار الفروقات
تسجيل التسوية
الكيانات
BankStatement
BankStatementLine
BankReconciliation
الحقول الأساسية لكشف البنك
id
bank_account_id
statement_date
opening_balance
closing_balance
imported_at
status
الحقول الأساسية لسطر كشف البنك
id
statement_id
txn_date
description
reference
debit_amount
credit_amount
balance
matched_transaction_id
match_status
قواعد الأعمال
لا يجوز اعتبار الحركة مسواة دون ربط
يجب الاحتفاظ بتاريخ وفاعل التسوية
يمكن أن توجد حركات معلقة
يمكن أن توجد رسوم بنكية لم تسجل بعد في النظام
الفروقات يجب أن تظهر بوضوح
6.10 Module J — Treasury Reports

هذه تقارير الخزينة الأساسية.

التقارير المطلوبة
Cashbox Ledger
Bank Account Ledger
Treasury Movement Report
Transfer Report
Unreconciled Transactions Report
Bank Reconciliation Summary
Liquidity Snapshot
المدخلات
organization
branch
treasury account
date range
currency
المخرجات
opening balance
inflows
outflows
transfers
closing balance
7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/
  treasury/
    cashboxes/
    bank_accounts/
    payment_methods/
    transactions/
    transfers/
    reconciliation/
    reports/
مثال تقسيم داخلي
treasury/transactions/
  models/
    treasury_transaction.py
  services/
    create_transaction.py
    post_transaction.py
    reverse_transaction.py
  selectors/
    transaction_queries.py
  api/
    serializers.py
    views.py
    urls.py
  validators/
    transaction_rules.py
  tests/
8. APIs المطلوبة في هذه المرحلة
8.1 Cashboxes
POST /api/v1/cashboxes/
GET /api/v1/cashboxes/
GET /api/v1/cashboxes/{id}/
PATCH /api/v1/cashboxes/{id}/
POST /api/v1/cashboxes/{id}/deactivate/
8.2 Bank Accounts
POST /api/v1/bank-accounts/
GET /api/v1/bank-accounts/
GET /api/v1/bank-accounts/{id}/
PATCH /api/v1/bank-accounts/{id}/
POST /api/v1/bank-accounts/{id}/deactivate/
8.3 Payment Methods
POST /api/v1/payment-methods/
GET /api/v1/payment-methods/
PATCH /api/v1/payment-methods/{id}/
8.4 Treasury Transactions
POST /api/v1/treasury-transactions/
GET /api/v1/treasury-transactions/
GET /api/v1/treasury-transactions/{id}/
PATCH /api/v1/treasury-transactions/{id}/
POST /api/v1/treasury-transactions/{id}/post/
POST /api/v1/treasury-transactions/{id}/reverse/
8.5 Transfers
POST /api/v1/treasury-transfers/
GET /api/v1/treasury-transfers/
GET /api/v1/treasury-transfers/{id}/
PATCH /api/v1/treasury-transfers/{id}/
POST /api/v1/treasury-transfers/{id}/post/
POST /api/v1/treasury-transfers/{id}/reverse/
8.6 Reconciliation
POST /api/v1/bank-statements/
GET /api/v1/bank-statements/
GET /api/v1/bank-statements/{id}/
POST /api/v1/bank-reconciliation/{id}/match/
POST /api/v1/bank-reconciliation/{id}/finalize/
8.7 Reports
GET /api/v1/cash-ledger/
GET /api/v1/bank-ledger/
GET /api/v1/treasury-movements/
GET /api/v1/unreconciled-transactions/
GET /api/v1/liquidity-summary/
9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — إنشاء صندوق
إنشاء صندوق رئيسي
ربطه بحساب محاسبي
تحديد الرصيد الافتتاحي

النتيجة المقبولة:
يمكن استخدام الصندوق في القبض والصرف.

سيناريو 2 — إنشاء حساب بنكي
إنشاء حساب بنك
ربطه بحساب أستاذ
تحديد بيانات البنك

النتيجة المقبولة:
يمكن استخدام الحساب البنكي في التحصيل والدفع.

سيناريو 3 — قبض نقدي
إنشاء حركة قبض للصندوق
تحديد الحساب المقابل
ترحيل الحركة

النتيجة المقبولة:

يزيد رصيد الصندوق
ينشأ قيد محاسبي صحيح
تسجل الحركة في Audit Log
سيناريو 4 — دفع من البنك
إنشاء حركة دفع من حساب بنكي
تحديد الحساب المقابل
ترحيل الحركة

النتيجة المقبولة:

ينخفض رصيد البنك
ينشأ القيد المحاسبي
يظهر أثر الحركة في كشف البنك
سيناريو 5 — تحويل من بنك إلى صندوق
إنشاء تحويل
تحديد المصدر والوجهة
ترحيل التحويل

النتيجة المقبولة:

ينخفض رصيد البنك
يزيد رصيد الصندوق
ينشأ قيد تحويل صحيح
سيناريو 6 — تسوية بنكية
إدخال كشف بنك
مطابقة الحركات
إظهار الفروقات
إنهاء التسوية

النتيجة المقبولة:

الحركات المطابقة تظهر مسواة
الحركات غير المطابقة تظهر منفصلة
يمكن تتبع الفروقات
10. قواعد الأعمال الملزمة
على مستوى الصندوق والبنك
لا يجوز الحركة على صندوق/بنك غير نشط
كل صندوق/بنك يجب أن يرتبط بحساب أستاذ
لا يجوز حذف كيان عليه حركات
يمكن تعطيله بدل حذفه
على مستوى الحركات
لا يجوز ترحيل حركة بدون جهة مالية
لا يجوز ترحيل حركة بمبلغ صفري أو سالب
لا يجوز الترحيل في فترة مغلقة
لا يجوز تعديل حركة بعد الترحيل
كل حركة مرحلة يجب أن تنتج قيدًا محاسبيًا
على مستوى التحويلات
لا يجوز أن يكون المصدر والوجهة نفس الحساب
لا يجوز تحويل مبلغ غير موجب
يجب تحديث الرصيدين معًا
يجب أن تكون العملة أو المعالجة واضحة
على مستوى التسوية
لا يجوز تعليم الحركة كمسواة بلا تطابق
يجب الاحتفاظ بسجل كامل للمطابقة
يجب أن تظهر الفروقات بوضوح
11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 cashboxes
id
organization_id
branch_id
code
name
currency
gl_account_id
opening_balance
current_balance
status
created_at
updated_at
11.2 bank_accounts
id
organization_id
branch_id
bank_name
account_name
account_number
iban
swift_code
currency
gl_account_id
opening_balance
current_balance
status
created_at
updated_at
11.3 payment_methods
id
code
name
type
is_active
11.4 treasury_transactions
id
organization_id
branch_id
transaction_number
transaction_date
transaction_type
treasury_source_type
treasury_source_id
payment_method_id
cashbox_id
bank_account_id
amount
currency
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
11.5 treasury_transfers
id
organization_id
branch_id
transfer_number
transfer_date
from_cashbox_id
from_bank_account_id
to_cashbox_id
to_bank_account_id
amount
currency
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
11.6 bank_statements
id
bank_account_id
statement_date
opening_balance
closing_balance
imported_at
status
11.7 bank_statement_lines
id
statement_id
txn_date
description
reference
debit_amount
credit_amount
balance
matched_transaction_id
match_status
11.8 bank_reconciliations
id
bank_account_id
statement_id
reconciled_by
reconciled_at
difference_amount
status
12. الترتيب التنفيذي داخل Phase 4
Sprint 1
cashboxes
bank_accounts
payment_methods
Sprint 2
treasury_transactions
cash in/out
bank in/out
Sprint 3
posting engine
balance updates
reversal rules
Sprint 4
transfers
transfer posting
transfer reversal
Sprint 5
bank statements
reconciliation engine
unmatched transactions flow
Sprint 6
treasury reports
liquidity summary
reconciliation summary
13. الاختبارات المطلوبة
Unit Tests
cashbox creation validation
bank account linkage validation
treasury transaction amount validation
transfer validation
posting preconditions
reconciliation matching rules
Integration Tests
create cash transaction → post → update balance
create bank transaction → post → update balance
create transfer → post → affect both sides
import bank statement → reconcile system transactions
Workflow Tests
full treasury cycle from receipt/payment to bank reconciliation
reverse incorrect treasury transaction
transfer between entities and verify reports
liquidity report consistency with ledger
14. شروط القبول قبل إغلاق Phase 4
Cashboxes
يمكن إنشاء صندوق وربطه بحساب أستاذ
يمكن استخدامه في الحركات
الرصيد يظهر بشكل صحيح
Bank Accounts
يمكن إنشاء حساب بنكي وربطه بحساب أستاذ
تظهر حركاته بشكل صحيح
الرصيد يتحدث بعد كل عملية
Treasury Transactions
يمكن تسجيل حركة قبض أو صرف
يمكن ترحيلها بنجاح
ينشأ القيد المحاسبي تلقائيًا
لا يمكن تعديلها بعد الترحيل
Transfers
يمكن إنشاء تحويل داخلي
يؤثر على المصدر والوجهة بدقة
ينشأ أثر محاسبي صحيح
Reconciliation
يمكن إدخال كشف بنك
يمكن مطابقة الحركات
تظهر الفروقات
يمكن إنهاء التسوية بشكل صحيح
Reports
Cash Ledger صحيح
Bank Ledger صحيح
Liquidity Summary صحيح
الحركات غير المسواة واضحة
15. ما الذي يعتبر فشلًا في هذه المرحلة؟

Phase 4 تعتبر غير مكتملة إذا:

اختلف رصيد الصندوق عن الحركات المرحلة
اختلف رصيد البنك عن الحركات المرحلة
أمكن ترحيل حركة بلا حساب مالي صحيح
أمكن تعديل حركة مرحلة
لم تؤثر التحويلات على الطرفين
فشلت التسوية البنكية في إظهار الفروقات
تقارير الخزينة لا تطابق الأستاذ العام
16. الخلاصة التنفيذية

بعد Phase 4 يصبح لديك:

محاسبة أساسية
مبيعات وتحصيل
مشتريات ودفع
خزينة وصندوق وبنوك
تحويلات داخلية
تسويات بنكية
صورة حقيقية للسيولة

وهنا يصبح النظام أقرب بكثير إلى نظام محاسبي تشغيلي متكامل.

17. الخطوة التالية المنطقية

بعد اكتمال واختبار Phase 4 بالكامل، الخطوة الأقوى هي:

Phase 5 — المخزون والأصناف والمستودعات Inventory & Stock

لأن المخزون هو الذي يربط:

الشراء
البيع
التكلفة
الجرد
تقييم المخزون
الربحية الفعلية

إذا أردت، أكتب لك Phase 5 الآن بنفس هذا المستوى التنفيذي.