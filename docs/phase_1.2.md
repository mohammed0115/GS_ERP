Phase 1 — بناء النواة المحاسبية Core Accounting Engine
1. اسم المرحلة

Phase 1: Core Accounting Foundation

2. الهدف من المرحلة

بناء الأساس المحاسبي الذي ستعتمد عليه كل العمليات اللاحقة مثل:

المبيعات
المشتريات
الصندوق
البنوك
المخزون
الضرائب
التقارير
الذكاء الاصطناعي

بمعنى آخر:
في هذه المرحلة لا نبني “نظام فواتير”، بل نبني المحرك الذي يجعل أي عملية مالية صحيحة وقابلة للتدقيق.

3. المخرجات النهائية المطلوبة من Phase 1

في نهاية هذه المرحلة يجب أن يكون لديك نظام قادر على:

إنشاء شركة
إنشاء فروع
إنشاء مستخدمين وأدوار
إعداد دليل الحسابات
تعريف أنواع الحسابات
إنشاء سنة مالية
إنشاء فترات مالية
فتح وإقفال الفترات
إدخال قيود يومية
التحقق من توازن القيود
ترحيل القيود
عكس القيود
منع التعديل في الفترات المغلقة
عرض دفتر الأستاذ
عرض ميزان المراجعة
تسجيل Audit Trail لكل عملية حساسة
4. حدود المرحلة
داخل النطاق
الشركات والفروع
المستخدمون والأدوار والصلاحيات
دليل الحسابات
أنواع الحسابات
السنوات والفترات المالية
القيود اليومية
سطور القيود
الترحيل
العكس
الأستاذ العام
ميزان المراجعة
السجل التدقيقي
خارج النطاق
العملاء
الموردون
فواتير البيع
فواتير الشراء
المخزون
الضرائب التفصيلية
البنوك والصندوق
AI
التقارير التنفيذية المتقدمة
5. فلسفة المرحلة

هذه المرحلة يجب أن تُبنى بهذه القاعدة:

القاعدة الذهبية

كل شيء لاحقًا يعتمد على هذا المحرك.

لذلك:

لا نكتب منطقًا سريعًا أو مؤقتًا
لا نخلط الواجهة مع منطق المحاسبة
لا نسمح بتجاوز قواعد الترحيل
لا نبني أي شاشة تشغيلية قبل اكتمال هذا الأساس
6. الموديولات التنفيذية داخل Phase 1
6.1 Module A — Organizations & Branches

هذا الموديول يعرّف الكيان الذي يعمل عليه النظام.

المطلوب
إنشاء شركة
تعديل بيانات الشركة
تفعيل/تعطيل الشركة
إنشاء فروع للشركة
ربط المستخدمين بالشركة والفروع
منع اختلاط بيانات الشركات
الكيانات
Organization
Branch
الحقول الأساسية للشركة
id
name
legal_name
code
status
default_currency
timezone
language
country
created_at
updated_at
الحقول الأساسية للفرع
id
organization_id
name
code
status
address
created_at
updated_at
قواعد الأعمال
كل فرع يجب أن يتبع شركة واحدة
لا يمكن لمستخدم رؤية بيانات شركة أخرى دون صلاحية
يمكن أن تكون هناك شركة رئيسية بعدة فروع
كل قيد محاسبي يجب أن ينتمي إلى شركة وفرع
6.2 Module B — Users, Roles, Permissions

هذا الموديول يضبط من يستطيع ماذا.

المطلوب
إنشاء مستخدم
إنشاء دور
ربط صلاحيات بالدور
ربط المستخدم بدور أو أكثر
تقييد الصلاحيات حسب الشركة/الفرع
الكيانات
User
Role
Permission
UserRole
RolePermission
أمثلة الأدوار
Admin
Accountant
Senior Accountant
Finance Manager
Auditor
أمثلة الصلاحيات
create_account
edit_account
create_journal_entry
post_journal_entry
reverse_journal_entry
close_period
reopen_period
view_reports
manage_users
قواعد الأعمال
لا يجوز منح صلاحيات مالية حساسة لكل المستخدمين
إقفال الفترة يحتاج صلاحية خاصة
ترحيل القيود يحتاج صلاحية مستقلة عن الإنشاء
عكس القيد يحتاج صلاحية أعلى
6.3 Module C — Chart of Accounts

هذا هو قلب النواة.

المطلوب
إنشاء أنواع الحسابات
إنشاء شجرة حسابات
دعم حسابات رئيسية وفرعية
تفعيل/تعطيل الحسابات
منع استخدام حسابات غير صالحة في القيود
الكيانات
AccountType
Account
أنواع الحسابات الأساسية
Asset
Liability
Equity
Revenue
Expense
الحقول الأساسية للحساب
id
organization_id
code
name_ar
name_en
parent_id
account_type_id
level
is_postable
is_active
normal_balance
created_at
updated_at
قواعد الأعمال
الكود يجب أن يكون فريدًا داخل الشركة
الحساب غير القابل للترحيل لا يقبل قيودًا مباشرة
الحسابات الفرعية فقط هي التي تستقبل الحركات غالبًا
لا يجوز حذف حساب عليه حركات
يمكن تعطيل الحساب بدل حذفه
يجب تحديد الطبيعة:
Debit normal
Credit normal
6.4 Module D — Fiscal Years & Periods

بدون هذا الموديول لا توجد رقابة حقيقية.

المطلوب
إنشاء سنة مالية
إنشاء فترات شهرية أو حسب السياسة
فتح الفترات
إقفال الفترات
إعادة فتح الفترة بصلاحية خاصة
الكيانات
FiscalYear
FiscalPeriod
الحقول الأساسية للسنة المالية
id
organization_id
name
start_date
end_date
status
الحقول الأساسية للفترة
id
fiscal_year_id
name
start_date
end_date
status
حالات الفترة
Open
Closed
Locked
قواعد الأعمال
لا تتداخل السنوات المالية
الفترات داخل نفس السنة لا تتداخل
لا يجوز الترحيل في فترة مغلقة
لا يجوز تعديل قيد مرحّل في فترة مغلقة
إعادة فتح الفترة يجب أن تسجل في Audit Log
6.5 Module E — Journal Entries

هذا هو المحرك الأساسي للقيود.

المطلوب
إنشاء قيد يدوي
إضافة سطور للقيد
التحقق من التوازن
حفظه كمسودة
ترحيله
عكسه
عرض تفاصيله
الكيانات
JournalEntry
JournalEntryLine
الحقول الأساسية للقيد
id
organization_id
branch_id
fiscal_period_id
entry_number
entry_date
reference
source_type
source_id
description
currency
status
total_debit
total_credit
posted_at
posted_by
reversed_from_id
created_by
created_at
updated_at
الحقول الأساسية لسطور القيد
id
journal_entry_id
account_id
description
debit_amount
credit_amount
cost_center_id
sequence
حالات القيد
Draft
Posted
Reversed
Cancelled
قواعد الأعمال
لا يرحل القيد إلا إذا كان متوازنًا
يجب أن يحتوي على سطرين على الأقل في الأغلب
لا يجوز أن يحتوي السطر على مدين ودائن معًا
لا يجوز أن يكون المبلغ صفريًا
لا يجوز استخدام حساب غير نشط
لا يجوز استخدام حساب غير قابل للترحيل
يجب أن يكون تاريخ القيد داخل فترة مالية صحيحة
لا يجوز تعديل القيد بعد الترحيل
العكس ينشئ قيدًا جديدًا معاكسًا، لا يعدل القديم
6.6 Module F — Posting Engine

هذا هو الجزء الذي ينقل القيد من Draft إلى Posted.

المطلوب
خدمة مركزية للترحيل
التحقق من الشروط
قفل القيد بعد الترحيل
تحديث أرصدة الأستاذ
حفظ حدث الترحيل
الخدمة الأساسية

PostJournalEntryService

مدخلات الخدمة
journal_entry_id
actor_id
تحقق الخدمة من:
وجود القيد
حالة القيد = Draft
توازن القيد
صلاحية المستخدم
أن الفترة مفتوحة
أن جميع الحسابات فعالة وقابلة للترحيل
مخرجات الخدمة
تغيير الحالة إلى Posted
تخزين posted_at
تخزين posted_by
تسجيل في Audit Log
6.7 Module G — Reversal Engine

هذا مهم جدًا للحوكمة.

المطلوب
عكس القيد المرحّل
إنشاء قيد مقابل بنفس السطور مع قلب المدين/الدائن
الربط بين القيد الأصلي والمعكوس
الخدمة الأساسية

ReverseJournalEntryService

مدخلاتها
journal_entry_id
reason
actor_id
reversal_date
قواعد الأعمال
لا يعكس إلا قيد مرحّل
لا يعكس القيد مرتين
يجب أن يكون تاريخ العكس في فترة مفتوحة
يجب تسجيل السبب
يجب الربط بين القيدين
6.8 Module H — General Ledger

هذا الموديول يوفر الحركات والأرصدة.

المطلوب
عرض حركة حساب
عرض رصيد افتتاحي
عرض الرصيد الجاري
الفلترة حسب:
شركة
فرع
حساب
فترة
تاريخ
المخرجات
كشف حساب
أرصدة نهائية
حركات تفصيلية
قاعدة احتساب الرصيد

الرصيد يعتمد على:

طبيعة الحساب
مجموع المدين
مجموع الدائن
الرصيد الافتتاحي
6.9 Module I — Trial Balance

هذا أول تقرير محاسبي جوهري.

المطلوب
استخراج ميزان مراجعة لفترة محددة
إظهار:
الحساب
الرصيد الافتتاحي
حركة المدين
حركة الدائن
الرصيد الختامي
قواعد الأعمال
يجب أن يكون مجموع المدين = مجموع الدائن
يجب دعم مستوى الحسابات
يجب دعم الفلترة بالشركة والفرع والفترة
6.10 Module J — Audit Log

بدون هذا الموديول لا يوجد نظام مالي محترف.

المطلوب

تسجيل الأحداث الحساسة مثل:

إنشاء حساب
تعديل حساب
تفعيل/تعطيل حساب
إنشاء قيد
تعديل مسودة
ترحيل قيد
عكس قيد
إقفال فترة
إعادة فتح فترة
تعديل صلاحيات
إنشاء مستخدم
الكيان
AuditLog
الحقول الأساسية
id
organization_id
actor_id
action
entity_type
entity_id
old_values
new_values
timestamp
ip_address
metadata
7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/
  platform/
    organizations/
    branches/
    users/
    roles/
    permissions/
    audit_logs/

  accounting/
    accounts/
    fiscal/
    journal/
    ledger/
    reports/
تقسيم كل موديول

داخل كل موديول يفضل الفصل إلى:

module/
  models/
  services/
  selectors/
  api/
  validators/
  tests/

مثال:

journal/
  models/
    journal_entry.py
    journal_entry_line.py
  services/
    create_entry.py
    post_entry.py
    reverse_entry.py
  selectors/
    entry_queries.py
  api/
    serializers.py
    views.py
    urls.py
  validators/
    entry_rules.py
  tests/
8. APIs المطلوبة في هذه المرحلة
8.1 Organizations
POST /api/v1/organizations/
GET /api/v1/organizations/
GET /api/v1/organizations/{id}/
PATCH /api/v1/organizations/{id}/
8.2 Branches
POST /api/v1/branches/
GET /api/v1/branches/
GET /api/v1/branches/{id}/
PATCH /api/v1/branches/{id}/
8.3 Roles & Permissions
POST /api/v1/roles/
GET /api/v1/roles/
PATCH /api/v1/roles/{id}/
GET /api/v1/permissions/
8.4 Accounts
POST /api/v1/accounts/
GET /api/v1/accounts/
GET /api/v1/accounts/{id}/
PATCH /api/v1/accounts/{id}/
POST /api/v1/accounts/{id}/deactivate/
8.5 Fiscal Years & Periods
POST /api/v1/fiscal-years/
GET /api/v1/fiscal-years/
POST /api/v1/fiscal-periods/
GET /api/v1/fiscal-periods/
POST /api/v1/fiscal-periods/{id}/close/
POST /api/v1/fiscal-periods/{id}/reopen/
8.6 Journal Entries
POST /api/v1/journal-entries/
GET /api/v1/journal-entries/
GET /api/v1/journal-entries/{id}/
PATCH /api/v1/journal-entries/{id}/
POST /api/v1/journal-entries/{id}/post/
POST /api/v1/journal-entries/{id}/reverse/
8.7 Ledger & Trial Balance
GET /api/v1/ledger/
GET /api/v1/trial-balance/
8.8 Audit Logs
GET /api/v1/audit-logs/
9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — إعداد شركة جديدة
إنشاء شركة
إنشاء فرعين
إنشاء مستخدم محاسب
منحه دور Accountant

النتيجة المقبولة:
المستخدم يرى فقط شركة/فروع صلاحياته.

سيناريو 2 — إعداد دليل الحسابات
إنشاء أنواع الحسابات
إنشاء حسابات رئيسية
إنشاء حسابات فرعية قابلة للترحيل

النتيجة المقبولة:
الحسابات تظهر في شجرة صحيحة، والحسابات غير المرحّلة لا تقبل حركة مباشرة.

سيناريو 3 — إنشاء سنة وفترة مالية
إنشاء سنة مالية
إنشاء 12 فترة شهرية
فتح الفترة الحالية

النتيجة المقبولة:
أي قيد بتاريخ خارج الفترة المفتوحة لا يرحل.

سيناريو 4 — إدخال قيد يدوي
إنشاء قيد Draft
إضافة سطر مدين
إضافة سطر دائن
حفظ
ترحيل

النتيجة المقبولة:
يتغير القيد إلى Posted ويظهر أثره في الأستاذ وميزان المراجعة.

سيناريو 5 — محاولة ترحيل قيد غير متوازن
إنشاء قيد
جعل المدين لا يساوي الدائن
محاولة الترحيل

النتيجة المقبولة:
الرفض مع رسالة واضحة.

سيناريو 6 — عكس قيد مرحّل
اختيار قيد Posted
تنفيذ Reverse
تحديد سبب العكس

النتيجة المقبولة:
يتم إنشاء قيد عكسي وربطه بالأصلي.

سيناريو 7 — إقفال فترة
إقفال الفترة
محاولة إنشاء/ترحيل قيد بتاريخ داخل الفترة المغلقة

النتيجة المقبولة:
الرفض إلا لصاحب صلاحية إعادة الفتح.

10. قواعد الأعمال الملزمة
على مستوى الحسابات
كود الحساب فريد داخل الشركة
لا يجوز حذف حساب عليه حركات
الحساب غير النشط لا يستخدم
الحساب غير المرحل إليه لا يقبل سطور قيود
على مستوى القيود
القيد لا يرحل إلا إذا توازن
لا تعديل على القيد المرحّل
كل قيد يجب أن يتبع فترة
لا ترحيل في فترة مغلقة
لا يمكن عكس قيد غير مرحّل
على مستوى الأمن
لا يمكن لمستخدم ترحيل قيد بلا صلاحية
لا يمكن رؤية بيانات شركة أخرى دون صلاحية
كل عملية حساسة تسجل في Audit Log
11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 organizations
id
name
legal_name
code
status
default_currency
timezone
language
created_at
updated_at
11.2 branches
id
organization_id
name
code
status
address
created_at
updated_at
11.3 roles
id
name
code
description
11.4 permissions
id
code
name
module
11.5 user_roles
id
user_id
role_id
organization_id
branch_id
11.6 account_types
id
organization_id
code
name
category
normal_balance
11.7 accounts
id
organization_id
code
name_ar
name_en
parent_id
account_type_id
level
is_postable
is_active
normal_balance
created_at
updated_at
11.8 fiscal_years
id
organization_id
name
start_date
end_date
status
11.9 fiscal_periods
id
fiscal_year_id
name
start_date
end_date
status
11.10 journal_entries
id
organization_id
branch_id
fiscal_period_id
entry_number
entry_date
reference
source_type
source_id
description
currency
status
total_debit
total_credit
posted_at
posted_by
reversed_from_id
created_by
created_at
updated_at
11.11 journal_entry_lines
id
journal_entry_id
account_id
description
debit_amount
credit_amount
sequence
11.12 audit_logs
id
organization_id
actor_id
action
entity_type
entity_id
old_values
new_values
timestamp
metadata
12. الترتيب التنفيذي داخل Phase 1
Sprint 1
organizations
branches
users
roles
permissions
Sprint 2
account_types
accounts
account tree
account validation
Sprint 3
fiscal_years
fiscal_periods
open/close/reopen
Sprint 4
journal_entries
journal_entry_lines
draft workflow
validations
Sprint 5
posting engine
reversal engine
immutability rules
Sprint 6
ledger queries
trial balance
audit logs
13. الاختبارات المطلوبة
Unit Tests
account code uniqueness
account activation validation
journal balance validation
period open/closed logic
posting preconditions
reversal rules
Integration Tests
create account hierarchy
create fiscal period and use it
create journal entry and post it
reverse posted entry
close period and block posting
Workflow Tests
setup company → accounts → year → period → entry → post → ledger → trial balance
14. شروط القبول لكل موديول
Organizations & Branches
يمكن إنشاء شركة وفرع بنجاح
البيانات معزولة
يمكن ربط المستخدم بفرع
Accounts
يمكن إنشاء شجرة حسابات سليمة
الحسابات غير المرحّلة لا تقبل قيدًا
لا يمكن تكرار الكود
Fiscal
يمكن فتح وإغلاق وإعادة فتح الفترات
لا يمكن الترحيل في فترة مغلقة
Journal
يمكن إنشاء قيد Draft
لا يمكن ترحيل قيد غير متوازن
يمكن ترحيل قيد متوازن
لا يمكن تعديل قيد مرحّل
Reversal
يمكن عكس قيد مرحّل مرة واحدة
ينتج قيد مقابل صحيح
Reports
ledger يعكس الحركات المرحلة فقط
trial balance متوازن
Audit
كل العمليات الحساسة مسجلة
15. ما الذي يعتبر فشلًا في هذه المرحلة؟

تعتبر Phase 1 غير مكتملة إذا حدث أي من الآتي:

يمكن ترحيل قيد غير متوازن
يمكن الترحيل في فترة مغلقة
يمكن تعديل قيد مرحّل
يمكن لمستخدم رؤية شركة أخرى بلا صلاحية
ledger لا يطابق journal entries
trial balance غير متوازن
audit log ناقص
16. الخلاصة التنفيذية

Phase 1 ليست مجرد بداية، بل هي الأساس الذي يحدد جودة المشروع كله.

إذا خرجت هذه المرحلة صحيحة، يصبح بناء:

العملاء
الموردين
الفواتير
القبض والصرف
الضرائب
التقارير
الذكاء الذكي

أسهل بكثير وأكثر أمانًا.

إذا خرجت ضعيفة، ستعيد بناء المشروع لاحقًا.

17. القرار التالي

بعد اكتمال واختبار Phase 1 بالكامل، ننتقل إلى:

Phase 2 — دورة المبيعات والتحصيل

وسيشمل:

العملاء
فواتير المبيعات
الإشعارات
التحصيل
أرصدة العملاء
الربط المحاسبي التلقائي مع النواة التي بنيناها هنا

الخطوة التالية المنطقية الآن هي أن أكتب لك Phase 2 بنفس هذا المستوى التنفيذي.

I prefer this response