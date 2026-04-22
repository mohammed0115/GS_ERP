Phase 2 — دورة المبيعات والتحصيل Sales & Receivables
1. اسم المرحلة
Phase 2: Sales, Invoicing & Receivables
2. الهدف من المرحلة
بناء دورة مبيعات كاملة تبدأ من العميل وتنتهي بالتحصيل والأثر المالي في الأستاذ العام.
في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


إنشاء العملاء


إدارة بياناتهم المالية


إصدار فواتير مبيعات


إصدار إشعارات دائنة ومدينة


تسجيل التحصيلات


تتبع أرصدة العملاء


إنتاج أعمار الديون


ترحيل الأثر المحاسبي تلقائيًا إلى Core Accounting



3. لماذا هذه المرحلة مهمة؟
هذه أول مرحلة تثبت أن النواة المحاسبية التي بنيتها في Phase 1 تعمل فعليًا في سيناريو تشغيلي حقيقي.
إذا نجحت هذه المرحلة، فهذا يعني أن النظام بدأ يتحول من:
محرك محاسبي داخلي
إلى:
منتج أعمال قابل للاستخدام اليومي

4. حدود المرحلة
داخل النطاق


العملاء


شروط الدفع


فواتير المبيعات


بنود الفاتورة


الخصومات


الضرائب الأساسية


الإشعارات الدائنة


الإشعارات المدينة


التحصيلات


تخصيص التحصيل على فاتورة أو أكثر


أرصدة العملاء


أعمار الديون


الترحيل المحاسبي التلقائي


خارج النطاق


عروض الأسعار


أوامر البيع


التوصيل والشحن


إدارة المرتجعات المعقدة


نقاط البيع


إدارة العقود المتقدمة


التكامل مع بوابات الدفع


CRM المتقدم


AI للتنبؤ بالمبيعات



5. المخرجات النهائية المطلوبة من Phase 2
في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


إنشاء عميل جديد


تعريف شروط الدفع والحد الائتماني


إصدار فاتورة مبيعات


احتساب الإجمالي والضريبة والخصم


حفظ الفاتورة كمسودة


اعتماد/إصدار الفاتورة


ترحيل القيد المحاسبي تلقائيًا


تسجيل تحصيل كامل أو جزئي


توزيع التحصيل على فاتورة أو عدة فواتير


إصدار إشعار دائن أو مدين


تحديث أرصدة العملاء تلقائيًا


عرض كشف حساب عميل


استخراج Aged Receivables


منع التحصيل أو التعديل الخاطئ بعد الإقفال أو في الحالات غير المسموح بها



6. الموديولات التنفيذية داخل Phase 2
6.1 Module A — Customers
هذا الموديول مسؤول عن تعريف العميل ماليًا وتشغيليًا.
المطلوب


إنشاء عميل


تعديل بيانات العميل


تفعيل/تعطيل العميل


تعريف الحد الائتماني


تعريف شروط الدفع


ربط العميل بحساب ذمم مدينة


عرض رصيد العميل


الكيان


Customer


الحقول الأساسية


id


organization_id


customer_code


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


credit_limit


payment_terms_days


receivable_account_id


revenue_account_id


tax_profile_id


status


created_at


updated_at


قواعد الأعمال


كود العميل فريد داخل الشركة


لا يجوز حذف عميل له حركات


يمكن تعطيل العميل بدل حذفه


كل عميل يجب أن يرتبط بحساب ذمم مدينة أو سياسة حساب افتراضية


يمكن تخصيص حساب إيراد افتراضي للعميل أو تركه على مستوى البنود



6.2 Module B — Sales Invoices
هذا هو مركز المرحلة.
المطلوب


إنشاء فاتورة مبيعات


إضافة بنود الفاتورة


احتساب المجاميع


احتساب الضريبة


حفظ كمسودة


إصدار الفاتورة


ترحيلها محاسبيًا


منع تعديل الفاتورة بعد الترحيل


الكيانات


SalesInvoice


SalesInvoiceLine


الحقول الأساسية للفاتورة


id


organization_id


branch_id


customer_id


invoice_number


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


sales_invoice_id


description


item_code


quantity


unit_price


discount_amount


tax_code_id


tax_amount


line_subtotal


line_total


revenue_account_id


sequence


حالات الفاتورة


Draft


Issued


Partially Paid


Paid


Cancelled


Credited


قواعد الأعمال


لا تصدر الفاتورة إذا لم يكن بها بند واحد على الأقل


لا يجوز أن تكون الكمية أو السعر سالبة


لا يجوز إصدار فاتورة لعميل غير نشط


لا يجوز تعديل فاتورة بعد إصدارها إذا كانت مرحّلة


يمكن حفظها Draft ثم إصدارها


عند الإصدار يجب إنشاء قيد محاسبي تلقائي


due_date يجب أن ينسجم مع invoice_date أو payment_terms


لا يجوز إصدار فاتورة في فترة مغلقة



6.3 Module C — Invoice Calculation Engine
هذا الجزء يجب أن يكون خدمة مستقلة لا منطقًا داخل الـ API.
المطلوب


احتساب إجمالي كل سطر


احتساب الخصومات


احتساب الضريبة


احتساب المجموع الكلي


إعادة الحساب عند أي تعديل


الخدمة الأساسية
CalculateSalesInvoiceTotalsService
المدخلات


invoice lines


tax rules


discount rules


المخرجات


subtotal


discount_total


tax_total


grand_total


قواعد الأعمال


الخصم قد يكون على السطر أو على الفاتورة


الضريبة يمكن أن تطبق بعد الخصم


التقريب المالي يجب أن يكون ثابتًا في كل النظام


لا نعتمد على حساب الواجهة فقط، بل على خدمة backend مركزية



6.4 Module D — Sales Posting Engine
هذا الموديول يربط الفاتورة بالمحاسبة.
المطلوب
عند إصدار الفاتورة:


إنشاء قيد محاسبي


ربطه بالفاتورة


تحديث حالة الفاتورة


منع التكرار


القيد المحاسبي القياسي
مثال شائع:
مدين: حساب العملاء
دائن: حساب الإيرادات
دائن: حساب ضريبة المخرجات إن وجدت
الخدمة الأساسية
PostSalesInvoiceService
المدخلات


sales_invoice_id


actor_id


التحقق


الفاتورة موجودة


حالتها Draft


العميل نشط


جميع البنود صحيحة


الفترة مفتوحة


حسابات الإيراد والعميل معرفة


المبالغ موجبة ومتناسقة


المخرجات


إنشاء JournalEntry


إنشاء JournalEntryLines


ربط journal_entry_id بالفاتورة


تغيير الحالة إلى Issued


تسجيل Audit Log


قواعد الأعمال


لا يمكن ترحيل الفاتورة مرتين


لا يمكن ترحيلها إذا لم تكن متوازنة حسابيًا


لا تعديل على البنود بعد الإصدار إلا عبر مسار نظامي مثل Credit Note



6.5 Module E — Receipts / Collections
هذا الموديول يسجل استلام الأموال من العملاء.
المطلوب


إنشاء سند قبض


ربط القبض بعميل


تخصيص التحصيل على فاتورة أو أكثر


دعم تحصيل كامل أو جزئي


دعم On Account collection


تحديث الأرصدة والفواتير


الكيانات


CustomerReceipt


CustomerReceiptAllocation


الحقول الأساسية لسند القبض


id


organization_id


branch_id


receipt_number


customer_id


receipt_date


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


receipt_id


sales_invoice_id


allocated_amount


حالات القبض


Draft


Posted


Cancelled


Reversed


قواعد الأعمال


لا يجوز تخصيص مبلغ أكبر من المتاح


لا يجوز تخصيص مبلغ أكبر من الرصيد المفتوح للفاتورة


يمكن ترك القبض غير مخصص On Account


لا يجوز تحصيل لعميل غير نشط


لا يجوز الترحيل في فترة مغلقة


القيد المحاسبي القياسي
عند التحصيل:
مدين: البنك/الصندوق
دائن: العملاء

6.6 Module F — Allocation Engine
هذا جزء حساس جدًا.
المطلوب


توزيع التحصيل على فاتورة واحدة أو عدة فواتير


تحديث الرصيد المفتوح لكل فاتورة


تحديث حالة الفاتورة


الخدمة الأساسية
AllocateReceiptService
النتائج المتوقعة


إذا غطى القبض كامل الفاتورة → الحالة Paid


إذا غطى جزءًا منها → Partially Paid


إذا لم يخصص → يبقى On Account balance


قواعد الأعمال


لا يجوز تخصيص على فاتورة ملغاة


لا يجوز التخصيص على فاتورة مدفوعة بالكامل


تخصيص التحصيل يجب أن يكون قابلاً للتتبع


يجب الاحتفاظ بسجل كامل لكل عملية تخصيص



6.7 Module G — Credit Notes
هذا الموديول يستخدم لتخفيض الذمم أو تعديل فاتورة بشكل نظامي.
المطلوب


إنشاء إشعار دائن مرتبط بفاتورة أو مستقل


تخفيض الرصيد على العميل


ترحيل أثر محاسبي معاكس للإيراد/الضريبة/الذمم


الكيانات


CreditNote


CreditNoteLine


الحقول الأساسية


id


organization_id


customer_id


related_invoice_id


note_number


note_date


reason


subtotal


tax_total


grand_total


status


journal_entry_id


حالات الإشعار الدائن


Draft


Issued


Applied


Cancelled


القيد المحاسبي الشائع
مدين: الإيراد
مدين: ضريبة المخرجات
دائن: العملاء
قواعد الأعمال


لا يمكن أن يتجاوز الإشعار الدائن الرصيد المفتوح المسموح


إذا كان مرتبطًا بفاتورة، يجب التحقق من الفاتورة


لا يجوز استخدامه كبديل لحذف الفاتورة



6.8 Module H — Debit Notes
هذا أقل استخدامًا من Credit Note لكنه مهم.
المطلوب


زيادة مستحقات العميل بشكل منظم


إنشاء أثر محاسبي إضافي


القيد المحاسبي الشائع
مدين: العملاء
دائن: الإيراد أو حساب تعديل مناسب
قواعد الأعمال


لا يستخدم عشوائيًا


يجب وجود سبب واضح


يجب اعتماد السياسات المحاسبية التي تسمح به



6.9 Module I — Customer Ledger / Statement
هذا يعرض حركة العميل بشكل واضح.
المطلوب


كشف حساب عميل


عرض الفواتير


عرض التحصيلات


عرض الإشعارات الدائنة/المدينة


عرض الرصيد الحالي


المدخلات


customer_id


date range


organization


branch


المخرجات


opening balance


invoices


receipts


credit notes


debit notes


closing balance



6.10 Module J — Aged Receivables
هذا تقرير أساسي لأي نظام مالي.
المطلوب


تصنيف أرصدة العملاء حسب عمر الدين


تصنيف مثل:


Current


1–30


31–60


61–90


90+




قواعد الأعمال


التقرير يعتمد على due_date


فقط الأرصدة المفتوحة تدخل في التقرير


يجب دعم الفلترة حسب الشركة والفرع والعميل



7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/  sales/    customers/    invoices/    receipts/    credit_notes/    debit_notes/    statements/    reports/

مثال تقسيم داخلي
sales/invoices/  models/    sales_invoice.py    sales_invoice_line.py  services/    calculate_totals.py    issue_invoice.py    cancel_invoice.py  selectors/    invoice_queries.py  api/    serializers.py    views.py    urls.py  validators/    invoice_rules.py  tests/

8. APIs المطلوبة في هذه المرحلة
8.1 Customers


POST /api/v1/customers/


GET /api/v1/customers/


GET /api/v1/customers/{id}/


PATCH /api/v1/customers/{id}/


POST /api/v1/customers/{id}/deactivate/


8.2 Sales Invoices


POST /api/v1/sales-invoices/


GET /api/v1/sales-invoices/


GET /api/v1/sales-invoices/{id}/


PATCH /api/v1/sales-invoices/{id}/


POST /api/v1/sales-invoices/{id}/issue/


POST /api/v1/sales-invoices/{id}/cancel/


8.3 Receipts


POST /api/v1/customer-receipts/


GET /api/v1/customer-receipts/


GET /api/v1/customer-receipts/{id}/


PATCH /api/v1/customer-receipts/{id}/


POST /api/v1/customer-receipts/{id}/post/


POST /api/v1/customer-receipts/{id}/allocate/


POST /api/v1/customer-receipts/{id}/reverse/


8.4 Credit Notes


POST /api/v1/credit-notes/


GET /api/v1/credit-notes/


GET /api/v1/credit-notes/{id}/


POST /api/v1/credit-notes/{id}/issue/


8.5 Debit Notes


POST /api/v1/debit-notes/


GET /api/v1/debit-notes/


GET /api/v1/debit-notes/{id}/


POST /api/v1/debit-notes/{id}/issue/


8.6 Statements & Reports


GET /api/v1/customer-statements/


GET /api/v1/aged-receivables/



9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — إنشاء عميل


إنشاء عميل جديد


تحديد شروط الدفع 30 يومًا


تحديد الحد الائتماني


ربطه بحساب الذمم


النتيجة المقبولة:
العميل جاهز للفوترة والتحصيل.

سيناريو 2 — إصدار فاتورة مبيعات


إنشاء فاتورة Draft


إضافة بنود


احتساب الإجمالي


إصدار الفاتورة


النتيجة المقبولة:


تتحول الحالة إلى Issued


ينشأ قيد محاسبي


يظهر الرصيد على العميل



سيناريو 3 — تحصيل جزئي


إنشاء سند قبض


تخصيص جزء من المبلغ لفاتورة


ترحيل القبض


النتيجة المقبولة:


حالة الفاتورة تصبح Partially Paid


الرصيد المفتوح ينخفض


القيد المحاسبي ينشأ بنجاح



سيناريو 4 — تحصيل كامل


إنشاء قبض


تخصيص المبلغ كاملًا


ترحيل العملية


النتيجة المقبولة:


الفاتورة تتحول إلى Paid


الذمم تنخفض


كشف الحساب يتحدث



سيناريو 5 — إصدار Credit Note


اختيار فاتورة


إنشاء إشعار دائن


إصداره


النتيجة المقبولة:


ينخفض رصيد العميل


ينشأ قيد محاسبي معاكس


يتم حفظ المرجع



سيناريو 6 — تقرير أعمار الديون


إنشاء عدة فواتير بتواريخ استحقاق مختلفة


تسجيل بعض التحصيلات


استخراج aged receivables


النتيجة المقبولة:
التقرير يصنف الأرصدة بدقة حسب العمر.

10. قواعد الأعمال الملزمة
على مستوى العملاء


لا يجوز استخدام عميل غير نشط


كود العميل فريد


لا يجوز حذف عميل له حركات


الحد الائتماني يجب أن يكون رقمًا موجبًا أو صفرًا


على مستوى الفواتير


لا يمكن إصدار فاتورة بلا بنود


لا يمكن إصدار فاتورة في فترة مغلقة


لا يجوز تعديل فاتورة بعد إصدارها إلا عبر مسار نظامي


كل فاتورة مصدرة يجب أن ترتبط بقيد محاسبي


due_date لا يسبق invoice_date


على مستوى التحصيل


لا يجوز تخصيص أكثر من المبلغ المدفوع


لا يجوز تخصيص أكثر من الرصيد المفتوح


لا يجوز تحصيل لعميل ملغى أو غير نشط


كل قبض مرحّل يجب أن ينتج قيدًا محاسبيًا


على مستوى الإشعارات


الإشعار الدائن لا يستخدم لحذف فاتورة


يجب أن يكون له سبب واضح


يجب أن يرتبط بسياسة محاسبية واضحة



11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 customers


id


organization_id


customer_code


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


credit_limit


payment_terms_days


receivable_account_id


revenue_account_id


status


created_at


updated_at


11.2 sales_invoices


id


organization_id


branch_id


customer_id


invoice_number


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


11.3 sales_invoice_lines


id


sales_invoice_id


description


item_code


quantity


unit_price


discount_amount


tax_code_id


tax_amount


line_subtotal


line_total


revenue_account_id


sequence


11.4 customer_receipts


id


organization_id


branch_id


receipt_number


customer_id


receipt_date


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


11.5 customer_receipt_allocations


id


receipt_id


sales_invoice_id


allocated_amount


11.6 credit_notes


id


organization_id


branch_id


customer_id


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


11.7 credit_note_lines


id


credit_note_id


description


quantity


unit_price


tax_code_id


tax_amount


line_total


revenue_account_id


sequence


11.8 debit_notes


id


organization_id


branch_id


customer_id


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



12. الترتيب التنفيذي داخل Phase 2
Sprint 1


customers


customer accounts linkage


customer validation


Sprint 2


sales invoices


invoice lines


totals engine


draft workflow


Sprint 3


invoice issuing


automatic posting


state transitions


Sprint 4


receipts


receipt posting


allocations


Sprint 5


credit notes


debit notes


balance adjustments


Sprint 6


customer statements


aged receivables


reconciliation checks



13. الاختبارات المطلوبة
Unit Tests


invoice totals calculation


due date generation


credit limit validation


receipt allocation validation


invoice posting validation


credit note posting validation


Integration Tests


create customer → issue invoice → create journal entry


create receipt → allocate → update invoice status


issue credit note → reduce receivable balance


aged receivables reflects open balances only


Workflow Tests


customer lifecycle from invoice to payment


partial payments across multiple invoices


reversing incorrect receipt or credit note


customer statement consistency with ledger



14. شروط القبول قبل إغلاق Phase 2
Customers


يمكن إنشاء عميل وتعديله وتعطيله


يمكن ربطه بحساب ذمم


Invoices


يمكن إنشاء فاتورة Draft


يمكن إصدارها بنجاح


ينشأ القيد المحاسبي آليًا


لا يمكن تعديلها بعد الإصدار بشكل غير نظامي


Receipts


يمكن تسجيل قبض كامل أو جزئي


يمكن تخصيصه بدقة


تتحدث حالة الفاتورة تلقائيًا


Credit/Debit Notes


يمكن إصدارها بشكل صحيح


تعدل الأرصدة بشكل مضبوط


تنتج أثرًا محاسبيًا صحيحًا


Reports


كشف حساب العميل صحيح


Aged Receivables صحيح


الأرصدة متطابقة مع الأستاذ العام



15. ما الذي يعتبر فشلًا في هذه المرحلة؟
Phase 2 تعتبر غير مكتملة إذا:


أصدرت فاتورة بلا قيد محاسبي


أمكن التحصيل بمبلغ يتجاوز الرصيد المفتوح


لم تتغير حالة الفاتورة بعد التحصيل


كشف حساب العميل لا يطابق ledger


تقرير أعمار الديون غير صحيح


أمكن تعديل فاتورة مصدرة بلا مسار نظامي


أمكن إصدار فاتورة في فترة مغلقة



16. الخلاصة التنفيذية
بعد Phase 2 يصبح لديك:


نواة محاسبية صحيحة


دورة مبيعات فعلية


ذمم عملاء


تحصيلات


كشف حساب


أعمار ديون


أثر مالي حقيقي


وهنا يبدأ النظام يأخذ شكل منصة محاسبية عملية، لا مجرد قاعدة بيانات محاسبية.

17. الخطوة التالية
بعد إكمال واختبار Phase 2 بالكامل، ننتقل منطقيًا إلى:
Phase 3 — دورة المشتريات والدفع Payables & Purchasing
وسيشمل:


الموردين


فواتير الشراء


الدفعات


إشعارات دائنة/مدينة للموردين


أعمار الدائنين


الربط المحاسبي التلقائي


الخطوة الصحيحة الآن هي كتابة Phase 3 بنفس المستوى التنفيذي.
