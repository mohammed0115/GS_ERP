قم بدور QA Lead + Accounting Systems Auditor.

راجع Phase 1 الخاصة بـ Core Accounting Engine.

نطاق الفحص:
- organizations
- branches
- users
- roles
- permissions
- chart of accounts
- account types
- fiscal years
- fiscal periods
- journal entries
- journal entry lines
- posting engine
- reversal engine
- general ledger
- trial balance
- audit logs

تحقق من:
- صحة إنشاء الشركات والفروع وعزل البيانات
- صحة الصلاحيات
- صحة شجرة الحسابات
- منع استخدام الحسابات غير النشطة أو غير القابلة للترحيل
- صحة إنشاء القيود
- منع ترحيل قيد غير متوازن
- منع الترحيل في فترة مغلقة
- صحة عكس القيد
- عدم قابلية تعديل القيد بعد الترحيل
- اتساق ledger مع journal entries
- اتساق trial balance
- وجود audit log لكل العمليات الحساسة

أخرج النتيجة بصيغة:
1. Scope Summary
2. Passed Checks
3. Failed Checks
4. Critical Bugs
5. Accounting Risks
6. Missing Test Cases
7. Required Fixes
8. Final Verdict