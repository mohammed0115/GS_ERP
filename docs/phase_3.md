Phase 3 — دورة المشتريات والدفع Payables & Purchasing
1. اسم المرحلة

Phase 3: Vendors, Purchase Invoices & Payables

2. الهدف من المرحلة

بناء دورة شراء مالية احترافية تبدأ من تعريف المورد، ثم تسجيل فاتورة الشراء، ثم تسجيل الدفع، مع الترحيل المحاسبي التلقائي إلى النواة التي بُنيت في Phase 1.

في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:

إنشاء الموردين
تعريف شروط الدفع للمورد
تسجيل فواتير الشراء
احتساب الضرائب والخصومات
ترحيل فواتير الشراء محاسبيًا
تسجيل دفعات الموردين
تخصيص الدفعات على فاتورة أو عدة فواتير
إصدار إشعارات دائنة ومدينة للموردين
عرض كشف حساب المورد
استخراج أعمار الدائنين Aged Payables
3. لماذا هذه المرحلة مهمة؟

هذه المرحلة تكمل التوازن الأساسي للنظام المحاسبي.

بعد اكتمالها، سيكون لديك:

دورة ذمم مدينة
دورة ذمم دائنة
قيود محاسبية ناتجة عن البيع والشراء
صورة مالية أكثر اكتمالًا

وبدون هذه المرحلة سيظل النظام ناقصًا حتى لو كانت المبيعات ممتازة.

4. حدود المرحلة
داخل النطاق
الموردون
شروط الدفع
فواتير الشراء
بنود الفاتورة
الخصومات
الضرائب الأساسية
دفعات الموردين
تخصيص الدفعات
الإشعارات الدائنة للمورد
الإشعارات المدينة للمورد
أرصدة الموردين
كشف حساب المورد
أعمار الدائنين
الترحيل المحاسبي التلقائي
خارج النطاق
طلبات الشراء
أوامر الشراء
الموافقات الشرائية المتقدمة
الاستلام المخزني
ثلاثة أطراف matching
العقود الشرائية
المناقصات
الشراء المتعدد المستودعات
AI تحليل الموردين
5. المخرجات النهائية المطلوبة من Phase 3

في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:

إنشاء مورد جديد
تحديد شروط دفعه
ربطه بحساب الذمم الدائنة
إنشاء فاتورة شراء Draft
احتساب الضرائب والخصومات
إصدار/اعتماد فاتورة الشراء
إنشاء القيد المحاسبي تلقائيًا
تسجيل دفعة كاملة أو جزئية
تخصيص الدفع على فاتورة أو أكثر
تخفيض رصيد المورد تلقائيًا
إصدار إشعار دائن للمورد
إصدار إشعار مدين للمورد
عرض كشف حساب المورد
استخراج تقرير Aged Payables
منع الدفع أو التعديل غير النظامي
6. الموديولات التنفيذية داخل Phase 3
6.1 Module A — Vendors

هذا الموديول يعرف المورد من الناحية التشغيلية والمالية.

المطلوب
إنشاء مورد
تعديل بيانات المورد
تفعيل/تعطيل المورد
تعريف شروط الدفع
تعريف العملة
ربط المورد بحساب ذمم دائنة
تحديد حساب مصروف/مشتريات افتراضي إن لزم
الكيان
Vendor
الحقول الأساسية
id
organization_id
vendor_code
name_ar
name_en
legal_name
tax_number
email
phone
address
city
country
currency
payment_terms_days
payable_account_id
default_expense_account_id
tax_profile_id
status
created_at
updated_at
قواعد الأعمال
كود المورد فريد داخل الشركة
لا يجوز حذف مورد له حركات
يمكن تعطيل المورد بدل حذفه
كل مورد يجب أن يرتبط بحساب ذمم دائنة أو سياسة افتراضية
يمكن تخصيص حسابات افتراضية مختلفة حسب نوع المورد
6.2 Module B — Purchase Invoices

هذا هو مركز المرحلة.

المطلوب
إنشاء فاتورة شراء
إضافة البنود
احتساب المجاميع
حفظ Draft
اعتماد/إصدار الفاتورة
ترحيلها محاسبيًا
الكيانات
PurchaseInvoice
PurchaseInvoiceLine
الحقول الأساسية للفاتورة
id
organization_id
branch_id
vendor_id
invoice_number
vendor_invoice_number
invoice_date
due_date
status
currency
exchange_rate
subtotal
discount_total
tax_total
grand_total
notes
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
الحقول الأساسية للبند
id
purchase_invoice_id
description
item_code
quantity
unit_price
discount_amount
tax_code_id
tax_amount
line_subtotal
line_total
expense_account_id
sequence
حالات الفاتورة
Draft
Issued
Partially Paid
Paid
Cancelled
Debited
Credited
قواعد الأعمال
لا يمكن إصدار فاتورة بلا بنود
لا يجوز أن تكون الكمية أو السعر سالبة
لا يجوز إصدار فاتورة لمورد غير نشط
لا يجوز إصدار فاتورة في فترة مغلقة
لا يجوز تعديل فاتورة مرحّلة
كل فاتورة شراء مصدرة يجب أن ترتبط بقيد محاسبي
due_date يجب أن ينسجم مع شروط الدفع
6.3 Module C — Purchase Calculation Engine

هذا موديول حسابي مستقل.

المطلوب
احتساب إجمالي البنود
احتساب الخصومات
احتساب الضريبة
احتساب الإجمالي الكلي
الخدمة الأساسية

CalculatePurchaseInvoiceTotalsService

المدخلات
invoice lines
discount rules
tax rules
المخرجات
subtotal
discount_total
tax_total
grand_total
قواعد الأعمال
التقريب المالي موحد مع النظام كله
الضريبة تطبق حسب القاعدة المحددة
الحساب يتم في backend لا على الواجهة فقط
لا يسمح بحفظ نتائج حسابية غير متناسقة
6.4 Module D — Purchase Posting Engine

هذا الموديول يربط فواتير الشراء بالمحاسبة.

المطلوب

عند إصدار فاتورة الشراء:

إنشاء قيد محاسبي
ربط القيد بالفاتورة
تحديث حالة الفاتورة
القيد المحاسبي الشائع

عند شراء مصروف أو مشتريات مباشرة:

مدين: حساب المصروف أو المشتريات
مدين: ضريبة المدخلات إن وجدت
دائن: الموردون

الخدمة الأساسية

PostPurchaseInvoiceService

المدخلات
purchase_invoice_id
actor_id
التحقق
الفاتورة موجودة
الحالة Draft
المورد نشط
البنود صالحة
الفترة مفتوحة
الحسابات معرّفة
المجاميع صحيحة
المخرجات
إنشاء JournalEntry
إنشاء JournalEntryLines
ربط القيد بالفاتورة
تغيير الحالة إلى Issued
تسجيل Audit Log
قواعد الأعمال
لا يجوز الترحيل مرتين
لا يجوز الترحيل في فترة مغلقة
لا يجوز إصدار الفاتورة دون حسابات سليمة
لا تعديل على الفاتورة بعد الإصدار إلا بمسار نظامي
6.5 Module E — Vendor Payments

هذا الموديول يسجل المدفوعات للموردين.

المطلوب
إنشاء دفعة مورد
ربطها بمورد
تخصيصها على فاتورة أو أكثر
دعم السداد الجزئي أو الكامل
دعم الدفع المسبق On Account
تحديث أرصدة الموردين
الكيانات
VendorPayment
VendorPaymentAllocation
الحقول الأساسية لدفعة المورد
id
organization_id
branch_id
payment_number
vendor_id
payment_date
amount
payment_method
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
الحقول الأساسية للتخصيص
id
payment_id
purchase_invoice_id
allocated_amount
حالات الدفعة
Draft
Posted
Cancelled
Reversed
قواعد الأعمال
لا يجوز تخصيص أكثر من المبلغ المدفوع
لا يجوز تخصيص أكثر من الرصيد المفتوح للفاتورة
يمكن ترك الدفعة كرصيد دائن للمورد On Account
لا يجوز الدفع لمورد غير نشط
لا يجوز الترحيل في فترة مغلقة
القيد المحاسبي الشائع

عند الدفع:
مدين: الموردون
دائن: البنك/الصندوق

6.6 Module F — Payment Allocation Engine

هذا جزء مهم جدًا في الذمم الدائنة.

المطلوب
توزيع الدفعة على فاتورة واحدة أو أكثر
تحديث الرصيد المفتوح لكل فاتورة
تحديث حالة الفاتورة
الخدمة الأساسية

AllocateVendorPaymentService

النتائج المتوقعة
إذا غطت الدفعة كامل الفاتورة → Paid
إذا غطت جزءًا منها → Partially Paid
إذا لم تخصص → On Account liability adjustment
قواعد الأعمال
لا يجوز التخصيص على فاتورة ملغاة
لا يجوز التخصيص على فاتورة مدفوعة بالكامل
يجب الاحتفاظ بسجل واضح لكل تخصيص
يجب أن ينعكس ذلك على كشف حساب المورد
6.7 Module G — Vendor Credit Notes

هذا الموديول يستخدم عندما يصدر المورد تخفيضًا أو تصحيحًا لصالح الشركة.

المطلوب
إنشاء إشعار دائن للمورد
تخفيض الالتزام تجاه المورد
ترحيل قيد محاسبي مناسب
الكيانات
VendorCreditNote
VendorCreditNoteLine
الحقول الأساسية
id
organization_id
vendor_id
related_invoice_id
note_number
note_date
reason
subtotal
tax_total
grand_total
status
journal_entry_id
القيد المحاسبي الشائع

مدين: الموردون
دائن: المصروف/المشتريات
دائن: ضريبة المدخلات إذا لزم

قواعد الأعمال
لا يجوز استخدام الإشعار الدائن كبديل لحذف فاتورة شراء
إذا كان مرتبطًا بفاتورة، يجب التحقق من الرصيد المتاح
يجب أن يكون السبب واضحًا
يجب أن ينتج أثرًا محاسبيًا صحيحًا
6.8 Module H — Vendor Debit Notes

هذا الموديول يستخدم في حالة زيادة مستحقة للمورد أو تعديلات إضافية.

المطلوب
إنشاء إشعار مدين للمورد
زيادة الالتزام تجاه المورد
ترحيل أثر محاسبي إضافي
القيد المحاسبي الشائع

مدين: مصروف/مشتريات
دائن: الموردون

قواعد الأعمال
لا يستخدم عشوائيًا
يجب أن يكون له سبب محاسبي واضح
يجب ضبط سياسات استخدامه
6.9 Module I — Vendor Statement

هذا التقرير يعرض حركة المورد كاملة.

المطلوب
عرض فواتير الشراء
عرض الدفعات
عرض الإشعارات
عرض الرصيد الحالي
عرض الرصيد الافتتاحي والختامي
المدخلات
vendor_id
date range
organization
branch
المخرجات
opening balance
purchase invoices
payments
credit notes
debit notes
closing balance
6.10 Module J — Aged Payables

هذا من أهم التقارير لإدارة الالتزامات.

المطلوب
تصنيف أرصدة الموردين حسب عمر الدين
تصنيف مثل:
Current
1–30
31–60
61–90
90+
قواعد الأعمال
يعتمد على due_date
فقط الأرصدة المفتوحة تدخل
يجب أن يدعم الشركة والفرع والمورد
7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/
  purchases/
    vendors/
    invoices/
    payments/
    credit_notes/
    debit_notes/
    statements/
    reports/
مثال تقسيم داخلي
purchases/invoices/
  models/
    purchase_invoice.py
    purchase_invoice_line.py
  services/
    calculate_totals.py
    issue_invoice.py
    cancel_invoice.py
  selectors/
    invoice_queries.py
  api/
    serializers.py
    views.py
    urls.py
  validators/
    invoice_rules.py
  tests/
8. APIs المطلوبة في هذه المرحلة
8.1 Vendors
POST /api/v1/vendors/
GET /api/v1/vendors/
GET /api/v1/vendors/{id}/
PATCH /api/v1/vendors/{id}/
POST /api/v1/vendors/{id}/deactivate/
8.2 Purchase Invoices
POST /api/v1/purchase-invoices/
GET /api/v1/purchase-invoices/
GET /api/v1/purchase-invoices/{id}/
PATCH /api/v1/purchase-invoices/{id}/
POST /api/v1/purchase-invoices/{id}/issue/
POST /api/v1/purchase-invoices/{id}/cancel/
8.3 Vendor Payments
POST /api/v1/vendor-payments/
GET /api/v1/vendor-payments/
GET /api/v1/vendor-payments/{id}/
PATCH /api/v1/vendor-payments/{id}/
POST /api/v1/vendor-payments/{id}/post/
POST /api/v1/vendor-payments/{id}/allocate/
POST /api/v1/vendor-payments/{id}/reverse/
8.4 Vendor Credit Notes
POST /api/v1/vendor-credit-notes/
GET /api/v1/vendor-credit-notes/
GET /api/v1/vendor-credit-notes/{id}/
POST /api/v1/vendor-credit-notes/{id}/issue/
8.5 Vendor Debit Notes
POST /api/v1/vendor-debit-notes/
GET /api/v1/vendor-debit-notes/
GET /api/v1/vendor-debit-notes/{id}/
POST /api/v1/vendor-debit-notes/{id}/issue/
8.6 Statements & Reports
GET /api/v1/vendor-statements/
GET /api/v1/aged-payables/
9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — إنشاء مورد
إنشاء مورد جديد
تحديد شروط الدفع 30 يومًا
ربطه بحساب الذمم الدائنة

النتيجة المقبولة:
المورد يصبح جاهزًا لفواتير الشراء والمدفوعات.

سيناريو 2 — إصدار فاتورة شراء
إنشاء فاتورة Draft
إضافة بنود
احتساب المجاميع
إصدار الفاتورة

النتيجة المقبولة:

تتحول الحالة إلى Issued
ينشأ قيد محاسبي
يظهر الالتزام على المورد
سيناريو 3 — دفع جزئي لمورد
إنشاء دفعة
تخصيص جزء منها لفاتورة شراء
ترحيل الدفعة

النتيجة المقبولة:

حالة الفاتورة تصبح Partially Paid
الرصيد المفتوح ينخفض
ينشأ القيد المحاسبي
سيناريو 4 — دفع كامل لمورد
إنشاء دفعة
تخصيص المبلغ كاملًا
ترحيل العملية

النتيجة المقبولة:

الفاتورة تتحول إلى Paid
الالتزام ينخفض
كشف حساب المورد يتحدث
سيناريو 5 — إصدار Vendor Credit Note
اختيار فاتورة شراء
إنشاء إشعار دائن من المورد
إصداره

النتيجة المقبولة:

ينخفض رصيد المورد المستحق
ينشأ قيد محاسبي صحيح
يتم حفظ المرجعية
سيناريو 6 — تقرير أعمار الدائنين
إنشاء عدة فواتير شراء بتواريخ استحقاق مختلفة
تسجيل بعض المدفوعات
استخراج Aged Payables

النتيجة المقبولة:
التقرير يصنف الالتزامات بدقة.

10. قواعد الأعمال الملزمة
على مستوى الموردين
لا يجوز استخدام مورد غير نشط
كود المورد فريد
لا يجوز حذف مورد له حركات
شروط الدفع يجب أن تكون صحيحة
على مستوى فواتير الشراء
لا يمكن إصدار فاتورة بلا بنود
لا يمكن إصدار فاتورة في فترة مغلقة
لا يجوز تعديل فاتورة بعد إصدارها دون مسار نظامي
كل فاتورة مصدرة يجب أن ترتبط بقيد محاسبي
due_date لا يسبق invoice_date
على مستوى المدفوعات
لا يجوز تخصيص أكثر من مبلغ الدفعة
لا يجوز تخصيص أكثر من الرصيد المفتوح
لا يجوز الدفع لمورد غير نشط
كل دفعة مرحلة تنتج قيدًا محاسبيًا
على مستوى الإشعارات
الإشعار الدائن لا يستخدم لحذف الفاتورة
يجب أن يكون السبب موثقًا
يجب أن يرتبط بسياسة مالية صحيحة
11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 vendors
id
organization_id
vendor_code
name_ar
name_en
legal_name
tax_number
email
phone
address
city
country
currency
payment_terms_days
payable_account_id
default_expense_account_id
status
created_at
updated_at
11.2 purchase_invoices
id
organization_id
branch_id
vendor_id
invoice_number
vendor_invoice_number
invoice_date
due_date
status
currency
exchange_rate
subtotal
discount_total
tax_total
grand_total
notes
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
11.3 purchase_invoice_lines
id
purchase_invoice_id
description
item_code
quantity
unit_price
discount_amount
tax_code_id
tax_amount
line_subtotal
line_total
expense_account_id
sequence
11.4 vendor_payments
id
organization_id
branch_id
payment_number
vendor_id
payment_date
amount
payment_method
reference
notes
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
11.5 vendor_payment_allocations
id
payment_id
purchase_invoice_id
allocated_amount
11.6 vendor_credit_notes
id
organization_id
branch_id
vendor_id
related_invoice_id
note_number
note_date
reason
subtotal
tax_total
grand_total
status
fiscal_period_id
journal_entry_id
created_by
created_at
updated_at
11.7 vendor_credit_note_lines
id
vendor_credit_note_id
description
quantity
unit_price
tax_code_id
tax_amount
line_total
expense_account_id
sequence
11.8 vendor_debit_notes
id
organization_id
branch_id
vendor_id
related_invoice_id
note_number
note_date
reason
subtotal
tax_total
grand_total
status
fiscal_period_id
journal_entry_id
12. الترتيب التنفيذي داخل Phase 3
Sprint 1
vendors
payable account linkage
vendor validation
Sprint 2
purchase invoices
invoice lines
totals engine
draft workflow
Sprint 3
invoice issuing
automatic posting
state transitions
Sprint 4
vendor payments
payment posting
allocations
Sprint 5
vendor credit notes
vendor debit notes
payable adjustments
Sprint 6
vendor statements
aged payables
reconciliation checks
13. الاختبارات المطلوبة
Unit Tests
purchase invoice totals calculation
due date generation
vendor payable validation
payment allocation validation
purchase invoice posting validation
vendor credit note posting validation
Integration Tests
create vendor → issue invoice → create journal entry
create payment → allocate → update invoice status
issue vendor credit note → reduce payable balance
aged payables reflects open balances only
Workflow Tests
vendor lifecycle from invoice to payment
partial payments across multiple invoices
reversing incorrect payment
vendor statement consistency with ledger
14. شروط القبول قبل إغلاق Phase 3
Vendors
يمكن إنشاء المورد وتعديله وتعطيله
يمكن ربطه بحساب ذمم دائنة
Purchase Invoices
يمكن إنشاء فاتورة Draft
يمكن إصدارها بنجاح
ينشأ القيد المحاسبي آليًا
لا يمكن تعديلها بعد الإصدار بشكل غير نظامي
Vendor Payments
يمكن تسجيل دفعة كاملة أو جزئية
يمكن تخصيصها بدقة
تتحدث حالة الفاتورة تلقائيًا
Credit/Debit Notes
يمكن إصدارها بشكل صحيح
تعدل الأرصدة بشكل مضبوط
تنتج أثرًا محاسبيًا صحيحًا
Reports
كشف حساب المورد صحيح
Aged Payables صحيح
الأرصدة متطابقة مع الأستاذ العام
15. ما الذي يعتبر فشلًا في هذه المرحلة؟

Phase 3 تعتبر غير مكتملة إذا:

صدرت فاتورة شراء بلا قيد محاسبي
أمكن دفع مبلغ يتجاوز الرصيد المفتوح
لم تتغير حالة الفاتورة بعد الدفع
كشف حساب المورد لا يطابق ledger
تقرير أعمار الدائنين غير صحيح
أمكن تعديل فاتورة شراء مصدرة بلا مسار نظامي
أمكن إصدار فاتورة شراء في فترة مغلقة
16. الخلاصة التنفيذية

بعد Phase 3 يصبح لديك:

ذمم مدينة
ذمم دائنة
مبيعات
مشتريات
قبض
صرف مرتبط بالموردين
كشف حساب عملاء وموردين
أعمار ديون وأعمار دائنين
محرك مالي بدأ يقترب من النظام المحاسبي الحقيقي

وهنا يصبح النظام مؤهلًا للدخول إلى الطبقة التالية المنطقية:
إدارة النقد والبنوك والصندوق أو المخزون بحسب الأولوية التجارية.

17. الخطوة التالية الأنسب

بعد إكمال واختبار Phase 3 بالكامل، عندك مساران منطقيان:

المسار A — Phase 4: Cash, Bank & Treasury

إذا كنت تريد ضبط:

الصندوق
الحسابات البنكية
التحويلات
التسويات
السيولة
المسار B — Phase 4: Inventory & Stock

إذا كان نشاطك يعتمد على:

الأصناف
المستودعات
تكلفة المخزون
الربط بين الشراء والبيع والمخزون

الأنسب غالبًا محاسبيًا هو البدء بـ Treasury أولًا ثم Inventory بعده، لأن البنك والصندوق يؤثران مباشرة على جميع العمليات.