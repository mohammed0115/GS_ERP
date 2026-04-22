Phase 1 — بناء النواة المحاسبية Core Accounting Engine
هذه أول مرحلة برمجية حقيقية.
وفيها لا نبني “نظام مبيعات كامل” ولا “مخزون” بعد، بل نبني القلب الذي سيحمل كل شيء لاحقًا.
أي خطأ هنا سيؤذي كل المراحل التالية.

1. هدف المرحلة
الهدف من Phase 1 هو بناء المحرك الذي يجعل النظام نظامًا محاسبيًا حقيقيًا لا مجرد شاشات إدخال.
في نهاية هذه المرحلة يجب أن يكون لديك نظام قادر على:


إنشاء شركة وفرع


إدارة المستخدمين والصلاحيات الأساسية


إنشاء دليل حسابات صحيح


إنشاء سنوات وفترات مالية


إدخال قيود يومية


ترحيل القيود


منع الترحيل الخاطئ


عرض دفتر الأستاذ


استخراج ميزان مراجعة


قفل فترة محاسبية


تسجيل كل العمليات المهمة في Audit Log



2. مبدأ المرحلة
في هذه المرحلة نبني 6 لبنات أساسية:
أ) Platform Foundation


الشركات


الفروع


المستخدمون


الأدوار


الصلاحيات


ب) Chart of Accounts


أنواع الحسابات


الحسابات الرئيسية والفرعية


هيكل الشجرة


ج) Fiscal Engine


السنة المالية


الفترات المحاسبية


الفتح والإقفال


د) Journal Engine


القيود اليومية


سطور القيود


التوازن


الترحيل


العكس


هـ) Ledger Engine


دفتر الأستاذ


أرصدة الحسابات


كشف الحساب


و) Audit & Control


السجل التدقيقي


تتبع المستخدمين


تتبع التعديلات


حماية الفترات المغلقة



3. حدود Phase 1
ما يدخل


Organizations


Branches


Users


Roles/Permissions


Account Types


Chart of Accounts


Fiscal Years


Fiscal Periods


Journal Entries


Journal Entry Lines


Posting Engine


General Ledger


Trial Balance


Audit Log


ما لا يدخل


العملاء


الموردون


فواتير المبيعات


فواتير الشراء


التحصيل والدفع


البنوك والصندوق


الضرائب التفصيلية


المخزون


الذكاء الاصطناعي


هذه ستأتي لاحقًا.
لو أدخلناها الآن سنشوّش المرحلة.

4. النتيجة النهائية المطلوبة
عند اكتمال Phase 1 يجب أن أستطيع تنفيذ هذا السيناريو:


إنشاء شركة


إنشاء فرع


إنشاء مستخدمين بصلاحيات مختلفة


إعداد دليل الحسابات


فتح سنة مالية


فتح فترة شهرية


إدخال قيد يومية متوازن


ترحيل القيد


رؤية الأثر في الأستاذ


رؤية الأثر في ميزان المراجعة


إغلاق الفترة


محاولة تعديل قيد في فترة مغلقة فتفشل


رؤية كل هذه الأحداث في Audit Log


إذا تحقق هذا السيناريو، فمرحلتنا ناجحة.

5. الموديولات التي سنبنيها في هذه المرحلة
5.1 Module: Organizations & Branches
الهدف
دعم تعدد الشركات والفروع من البداية.
الكيانات
Organization


id


name


legal_name


code


country


currency_code


status


created_at


updated_at


Branch


id


organization_id


name


code


city


address


status


قواعد الأعمال


كل فرع يجب أن ينتمي إلى شركة واحدة


المستخدم لا يرى إلا الشركة/الفروع المصرح له بها


كل حساب وكل قيد وكل فترة يجب أن ترتبط بشركة


الفرع قد يكون مطلوبًا أو اختياريًا حسب سياسة النظام، لكني أنصح أن يكون موجودًا من البداية


APIs الأساسية


POST /organizations


GET /organizations


GET /organizations/{id}


POST /branches


GET /branches


GET /branches/{id}



5.2 Module: Users, Roles, Permissions
الهدف
ضبط الوصول للنظام المالي بشكل صارم.
الكيانات
User


id


organization_id


full_name


email


password_hash


is_active


last_login


Role


id


organization_id


name


code


Permission


id


code


name


module


UserRole


user_id


role_id


RolePermission


role_id


permission_id


الأدوار الأولية


Admin


Accountant


SeniorAccountant


FinanceManager


Auditor


الصلاحيات الأساسية


create_account


edit_account


create_journal_entry


approve_journal_entry


post_journal_entry


reverse_journal_entry


view_ledger


view_trial_balance


open_period


close_period


manage_users


view_audit_logs


قواعد الأعمال


لا يرحّل القيد إلا مستخدم لديه صلاحية الترحيل


لا يغلق الفترة إلا مستخدم مخول


لا يرى المستخدم بيانات شركة أخرى


المدقق قد يرى دون أن يعدل


APIs الأساسية


POST /users


GET /users


POST /roles


GET /roles


POST /roles/{id}/permissions


POST /users/{id}/roles



5.3 Module: Account Types & Chart of Accounts
الهدف
بناء دليل حسابات صحيح ومرن.
الكيانات
AccountType


id


code


name


category
مثل:


asset


liability


equity


revenue


expense




Account


id


organization_id


parent_id


account_type_id


code


name_ar


name_en


level


is_group


is_postable


status


normal_balance


debit


credit




قواعد الأعمال


الحساب التجميعي is_group=true لا يقبل قيودًا مباشرة


الحساب القابل للترحيل is_postable=true فقط هو الذي يستخدم داخل سطور القيود


لكل حساب parent واحد كحد أقصى


أكواد الحسابات يجب أن تكون فريدة داخل الشركة


لا يسمح بجعل الحساب Parent لنفسه أو تكوين حلقة دائرية


لا يحذف الحساب إذا كان عليه حركات


الحسابات الأساسية لا تعدّل عشوائيًا بعد الاعتماد


مثال هيكل مبدئي


1000 الأصول


1100 الأصول المتداولة


1110 الصندوق


1120 البنك


1130 العملاء






2000 الالتزامات


3000 حقوق الملكية


4000 الإيرادات


5000 المصروفات


APIs الأساسية


POST /account-types


GET /account-types


POST /accounts


GET /accounts


GET /accounts/tree


PATCH /accounts/{id}


POST /accounts/{id}/deactivate



5.4 Module: Fiscal Years & Periods
الهدف
تثبيت الزمن المحاسبي الرسمي للنظام.
الكيانات
FiscalYear


id


organization_id


name


start_date


end_date


status


draft


open


closed




FiscalPeriod


id


fiscal_year_id


period_name


start_date


end_date


status


open


closed


locked




قواعد الأعمال


لا يجوز تداخل سنتين ماليتين لنفس الشركة


لا يجوز تداخل الفترات


كل قيد يجب أن يقع داخل فترة مالية مفتوحة


لا يسمح بالترحيل في فترة مغلقة


إعادة فتح الفترة يجب أن تكون بصلاحية خاصة جدًا


يمكن اعتماد التقسيم الشهري تلقائيًا عند إنشاء السنة المالية


APIs الأساسية


POST /fiscal-years


GET /fiscal-years


POST /fiscal-years/{id}/open


POST /fiscal-years/{id}/periods/generate


GET /fiscal-periods


POST /fiscal-periods/{id}/close


POST /fiscal-periods/{id}/reopen



5.5 Module: Journal Entries
الهدف
بناء قلب القيود اليومية.
الكيانات
JournalEntry


id


organization_id


branch_id


fiscal_year_id


fiscal_period_id


entry_number


entry_date


reference_type


reference_id


source


memo


status


currency_code


total_debit


total_credit


created_by


approved_by


posted_by


posted_at


JournalEntryLine


id


journal_entry_id


account_id


description


debit_amount


credit_amount


line_order


حالات القيد


draft


submitted


approved


posted


reversed


cancelled


Rules مهمة جدًا


لا يمكن ترحيل قيد غير متوازن


لا يمكن أن يكون السطر مدينًا ودائنًا في نفس الوقت


يجب أن يحتوي القيد على سطرين على الأقل


لا يسمح بسالب في debit أو credit


لا يسمح بالحذف بعد الترحيل


التعديل بعد الترحيل ممنوع


الإلغاء قبل الترحيل مسموح حسب الصلاحيات


بعد الترحيل، يتم العكس عبر Reverse Entry وليس Edit/Delete


رقم القيد يجب أن يكون فريدًا داخل الشركة


لا يسمح بالترحيل إن كانت الفترة مغلقة


لا يسمح بالترحيل على حساب غير قابل للترحيل


لا يسمح باستخدام حساب غير نشط


أنواع المصادر source


manual


opening_balance


adjustment


system_seed


في Phase 1 نبدأ بهذه فقط.
APIs الأساسية


POST /journal-entries


GET /journal-entries


GET /journal-entries/{id}


PATCH /journal-entries/{id}


POST /journal-entries/{id}/submit


POST /journal-entries/{id}/approve


POST /journal-entries/{id}/post


POST /journal-entries/{id}/reverse


POST /journal-entries/{id}/cancel



5.6 Module: Posting Engine
الهدف
فصل “إنشاء القيد” عن “اعتماد الأثر النهائي”.
في هذه المرحلة يمكن تنفيذ الترحيل داخل نفس التطبيق، لكن كـ service مستقلة واضحة.
مسؤوليات Posting Engine


التحقق من توازن القيد


التحقق من صحة الحسابات


التحقق من صلاحية الفترة


تغيير الحالة إلى posted


تثبيت totals


إنشاء أثر الأستاذ


تسجيل الحدث في Audit Log


ما لا يفعله


لا يولد قيود المبيعات أو الشراء بعد


لا يتعامل مع الضرائب بعد


لا يختلط بمنطق UI


Service مقترحة


JournalValidationService


JournalApprovalService


JournalPostingService


JournalReverseService



5.7 Module: General Ledger
الهدف
إظهار حركة الحسابات بطريقة محاسبية صحيحة.
ما يجب أن يدعمه


جلب حركات حساب معين


حساب الرصيد الافتتاحي


حساب الرصيد الجاري


فلترة حسب:


الشركة


الفرع


الحساب


الفترة


التاريخ




كشف حساب مرتب زمنيًا


الكيان المنطقي
يمكن أن تحسب حركات الأستاذ من قيود المرحلة، أو تنشئ جدول snapshot/performance لاحقًا.
في Phase 1 أنصح أن تبدأ من القيود نفسها كمصدر حقيقة.
API أساسية


GET /ledger/accounts/{account_id}


GET /ledger/accounts/{account_id}/statement


GET /ledger/summary



5.8 Module: Trial Balance
الهدف
إعطاء صورة مجمعة للأرصدة.
ما يجب أن يدعمه


ميزان مراجعة لفترة


opening / movement / ending


تجميع حسب الحساب


فرز حسب كود الحساب


إمكانية إظهار فقط الحسابات التي عليها حركة


قواعد


يعتمد فقط على القيود المرحلة


لا يدخل draft ولا submitted


يحتسب حسب الفترة والتواريخ المحددة


APIs


GET /reports/trial-balance


GET /reports/trial-balance/export



5.9 Module: Audit Log
الهدف
أي فعل مالي مهم يجب أن يترك أثرًا واضحًا.
الكيان
AuditLog


id


organization_id


user_id


entity_type


entity_id


action


old_values_json


new_values_json


ip_address


user_agent


created_at


الأفعال التي يجب تسجيلها


إنشاء حساب


تعديل حساب


تعطيل حساب


فتح سنة مالية


إغلاق فترة


إنشاء قيد


تعديل قيد draft


اعتماد قيد


ترحيل قيد


عكس قيد


إنشاء مستخدم


تعديل صلاحيات


APIs


GET /audit-logs


GET /audit-logs/{id}



6. قاعدة البيانات المبدئية لهذه المرحلة
الجداول الأساسية


organizations


branches


users


roles


permissions


role_permissions


user_roles


account_types


accounts


fiscal_years


fiscal_periods


journal_entries


journal_entry_lines


audit_logs


جداول اختيارية من الآن


currencies


organization_settings


user_branch_access


أنا أنصح بإضافة organization_settings من البداية لأنها ستفيد لاحقًا.

7. العلاقات الحرجة
Organization
ترتبط بـ:


branches


users


accounts


fiscal_years


journal_entries


audit_logs


Account
يرتبط بـ:


account_type


parent_account


journal_entry_lines


FiscalYear
يرتبط بـ:


fiscal_periods


journal_entries


JournalEntry
يرتبط بـ:


organization


branch


fiscal_year


fiscal_period


user


journal_entry_lines



8. منطق حالات القيد
هذا مهم جدًا، لأنه يمنع الفوضى.
Draft


يمكن التعديل


يمكن الإلغاء


لا يظهر في التقارير


Submitted


جاهز للمراجعة


لا يفترض تعديله إلا بإرجاعه Draft


Approved


معتمد للمحاسبة


جاهز للترحيل


Posted


نهائي


يدخل الأستاذ وميزان المراجعة


لا يعدل ولا يحذف


Reversed


القيد الأصلي أصبح معكوسًا


يبقى محفوظًا تاريخيًا


Cancelled


ألغي قبل الترحيل



9. التسلسل العملي الذي يجب برمجته
الترتيب مهم. لا تبدأ عشوائيًا.
Sprint 1 داخل Phase 1
Platform base


organizations


branches


users


roles


permissions


auth


organization scoping


اختبار القبول


إنشاء شركة


إنشاء فرع


إنشاء مستخدم محاسب


منع المستخدم من رؤية شركة أخرى



Sprint 2 داخل Phase 1
Chart of Accounts


account types


account model


account tree


validation rules


اختبار القبول


إنشاء شجرة حسابات


منع التكرار في الأكواد


منع الترحيل على حساب تجميعي



Sprint 3 داخل Phase 1
Fiscal engine


fiscal years


period generation


open/close/reopen controls


اختبار القبول


إنشاء سنة مالية


توليد 12 فترة


إغلاق فترة


منع الترحيل في فترة مغلقة



Sprint 4 داخل Phase 1
Journal engine


entry creation


lines


status machine


submit/approve/post/reverse


اختبار القبول


إنشاء قيد متوازن


رفض قيد غير متوازن


ترحيل قيد صحيح


عكس قيد مرحل



Sprint 5 داخل Phase 1
Ledger + Trial Balance + Audit Logs


account statement


trial balance


audit history


اختبار القبول


ظهور الأثر في الأستاذ


ظهور الأثر في ميزان المراجعة


تسجيل كل الأحداث المهمة في audit log



10. الواجهات البرمجية API Contract Direction
لن أعطيك OpenAPI كامل الآن، لكن هذا الهيكل الصحيح:
Platform


POST /api/v1/organizations


POST /api/v1/branches


POST /api/v1/users


POST /api/v1/roles


Accounting setup


POST /api/v1/account-types


POST /api/v1/accounts


GET /api/v1/accounts/tree


Fiscal


POST /api/v1/fiscal-years


POST /api/v1/fiscal-years/{id}/periods/generate


POST /api/v1/fiscal-periods/{id}/close


Journals


POST /api/v1/journal-entries


POST /api/v1/journal-entries/{id}/submit


POST /api/v1/journal-entries/{id}/approve


POST /api/v1/journal-entries/{id}/post


POST /api/v1/journal-entries/{id}/reverse


Reports


GET /api/v1/ledger/accounts/{account_id}


GET /api/v1/reports/trial-balance



11. قواعد الأعمال الحرجة
هذه لا بد أن تكون مكتوبة داخل الكود والاختبارات:
الحسابات


الكود فريد داخل الشركة


الحساب التجميعي لا يستقبل قيودًا


الحساب غير النشط لا يستخدم


parent و child يجب أن يكونا من نفس الشركة


الفترات


لا تداخل


لا ترحيل خارج فترة مفتوحة


لا إعادة فتح بدون صلاحية


القيود


متوازن


على الأقل سطران


المدين = الدائن


no negative values


no zero-only entry


لا تعديل بعد الترحيل


لا حذف بعد الترحيل


العكس يتم بقيد عكسي


التقارير


تعتمد فقط على posted entries


أي draft أو cancelled أو submitted لا يدخل



12. Strategy الاختبارات
12.1 Unit Tests
اختبر:


account tree validation


unique account code


journal balancing


status transition rules


period open/close rules


reverse entry generation


أمثلة


هل يرفض النظام قيدًا 100 مدين / 90 دائن


هل يرفض ترحيل قيد على حساب is_group=true


هل يمنع تعديل posted entry


هل يمنع الترحيل في period مغلقة



12.2 Integration Tests
اختبر:


create org → create accounts → create fiscal year → create journal → post → ledger/trial balance updated


reverse posted entry → balances updated correctly


close period → post in same period fails



12.3 Workflow Tests
سيناريو كامل:


Admin ينشئ الشركة


Accountant ينشئ دليل الحسابات


FinanceManager يفتح السنة


Accountant يجهز قيد


SeniorAccountant يعتمده


FinanceManager يرحله


Auditor يراجع الأثر



12.4 Security Tests


مستخدم شركة A لا يرى Company B


مستخدم بلا صلاحية post لا يستطيع الترحيل


مستخدم بلا صلاحية close_period لا يغلق الفترة



13. معايير القبول الصارمة للخروج من Phase 1
لا ننتقل إلى Phase 2 إلا إذا تحقق التالي:
Functional Acceptance


إنشاء شركة وفرع ومستخدمين بنجاح


إنشاء شجرة حسابات سليمة


إنشاء سنة وفترات


إدخال قيد متوازن


ترحيل القيد


عكس القيد


رؤية الأستاذ


استخراج ميزان المراجعة


إغلاق الفترة ومنع الترحيل فيها


تسجيل الأثر في Audit Log


Data Integrity Acceptance


لا توجد قيود مرحلة غير متوازنة


لا توجد حركات على حسابات غير postable


لا توجد قيود في فترات مغلقة


لا يوجد اختراق بين الشركات


Test Acceptance


نجاح كل Unit tests الأساسية


نجاح كل Integration tests الأساسية


نجاح سيناريو واحد كامل على الأقل end-to-end داخل النظام


Architecture Acceptance


services منفصلة عن views


business rules ليست مبعثرة في الواجهة


status machine واضحة


model constraints موجودة


audit logging موجود



14. ما الذي يجب ألا نفعله في هذه المرحلة


لا نبني sales invoice الآن


لا نبني purchase invoice الآن


لا نبني tax engine معقد الآن


لا نبني AI الآن


لا نبدأ dashboard كبيرة الآن


لا نكثر الواجهات قبل ثبات المحرك


في هذه المرحلة نحن نبني الأساس الذي سيمنع انهيار المشروع.

15. مخرجات Phase 1
في نهاية هذه المرحلة يجب أن تخرج بـ:
برمجيًا


Modules أساسية شغالة


APIs أساسية شغالة


قاعدة بيانات سليمة


اختبارات ناجحة


توثيقيًا


ERD محدث


API docs أولية


Roles/permissions matrix


accounting rules doc


acceptance checklist



16. تعريف النجاح الحقيقي
إذا انتهت Phase 1 وأصبح بإمكانك القول:

لدي محرك محاسبي يستطيع استقبال قيود صحيحة، ترحيلها، قفل الفترات، وحساب أثرها بدقة داخل الأستاذ وميزان المراجعة مع سجل تدقيقي كامل.

فهنا فقط نقول:
النظام بدأ يصبح نظامًا محاسبيًا حقيقيًا.

17. ماذا بعد Phase 1
بعد اجتيازها ننتقل إلى:
Phase 2 — Sales & Receivables
وفيها سندخل:


customers


sales invoices


credit notes


receipts


receivables aging


auto-posting from sales docs to journal


لكن لا أنصح إطلاقًا بالانتقال قبل ثبات هذه المرحلة.

18. توجيهي لك كمرشد تنفيذ
أنصحك الآن أن تتعامل مع Phase 1 بهذه القاعدة:
لا تفتح Sprint جديدًا حتى ينجح اختبار الـ Sprint الحالي بالكامل.
الترتيب الذي أراه صحيحًا:


Platform base


Chart of accounts


Fiscal engine


Journal engine


Ledger & trial balance


Audit log


Full acceptance test


الخطوة التالية الصحيحة الآن هي أن أكتب لك Phase 1 على شكل برومبتات تنفيذية مرتبة لـ Codex/Claude بحيث يبدأ التطوير Sprint by Sprint بدون تخبط.I prefer this response