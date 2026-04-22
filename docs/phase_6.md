Phase 6 — الضرائب، الإقفال المالي، والتقارير الرسمية
Tax, Financial Closing & Official Financial Reporting
1. اسم المرحلة
Phase 6: Tax Engine, Period Closing, Adjustments & Financial Statements
2. الهدف من المرحلة
بناء الطبقة التي تضبط:


الضرائب


التسويات


قيود نهاية الفترة


الإقفال المالي


التقارير الرسمية


المراجعات النهائية قبل إصدار القوائم


في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


تعريف أنواع الضرائب


احتساب الضرائب على البيع والشراء


تتبع الضريبة المستحقة والضريبة القابلة للخصم


إصدار تقارير ضريبية


إنشاء قيود تسوية


إقفال الفترات والشهور


تنفيذ قيود الإقفال


إعداد القوائم المالية الرسمية


إصدار ميزان مراجعة قبل وبعد الإقفال


منع أي عبث بعد الإقفال إلا عبر صلاحيات خاصة ومسار منضبط



3. لماذا هذه المرحلة مهمة؟
حتى الآن، النظام أصبح ينجز:


بيع


شراء


قبض


دفع


بنك


صندوق


مخزون


لكن الإدارة المالية لا تكتفي بالحركة اليومية.
هي تحتاج إلى:


ما الضريبة المستحقة؟


ما الضريبة القابلة للخصم؟


هل الفترة جاهزة للإغلاق؟


ما التسويات المطلوبة؟


ما صافي الربح الحقيقي؟


ما القوائم المالية الرسمية؟


وهذا كله هو دور Phase 6.

4. حدود المرحلة
داخل النطاق


Tax Codes


Tax Engine


Output Tax / Input Tax tracking


Tax reports


period-end adjustments


accruals & prepayments basics


depreciation hooks if fixed assets later


closing checklist


period close/reopen governance


closing journal entries


profit/loss closing


retained earnings transfer


official financial statements


financial report mapping


خارج النطاق


إقرار ضريبي حكومي مباشر متكامل


تكامل مباشر مع منصات حكومية


معالجة ضريبية دولية معقدة متعددة الولايات


Consolidation متعدد الشركات المتقدم


Budgeting


Forecasting


Advanced management accounting


Group reporting


IFRS engine كامل آلي



5. المخرجات النهائية المطلوبة من Phase 6
في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


تعريف أنواع وأكواد الضرائب


ربط الضرائب ببنود البيع والشراء


احتساب ضريبة المخرجات والمدخلات


إنشاء ملخص ضريبي للفترة


استخراج تقرير ضريبة المبيعات


استخراج تقرير ضريبة المشتريات


تنفيذ قيود تسوية يدوية


تنفيذ تسويات نهاية الفترة


تشغيل Checklist للإقفال


إغلاق الفترة ماليًا


منع أي ترحيل جديد داخل الفترة المغلقة


إصدار قائمة الدخل


إصدار المركز المالي


إصدار ميزان المراجعة


إصدار دفتر الأستاذ النهائي للفترة


إنشاء قيود إقفال الأرباح والخسائر


ترحيل صافي الربح إلى الأرباح المبقاة أو الحساب المحدد



6. الموديولات التنفيذية داخل Phase 6
6.1 Module A — Tax Codes & Tax Profiles
هذا الموديول يعرف منطق الضريبة في النظام.
المطلوب


إنشاء أكواد ضريبية


تحديد نوع الضريبة


تحديد النسبة


تحديد التطبيق على:


البيع


الشراء


كلاهما




ربط حسابات الضريبة المحاسبية


دعم حالات الإعفاء والصفرية إن لزم


الكيانات


TaxCode


TaxProfile


الحقول الأساسية لـ TaxCode


id


organization_id


code


name_ar


name_en


tax_type


rate


applies_to


output_tax_account_id


input_tax_account_id


is_active


created_at


updated_at


الحقول الأساسية لـ TaxProfile


id


organization_id


name


default_sales_tax_code_id


default_purchase_tax_code_id


is_active


قواعد الأعمال


كل كود ضريبي يجب أن يحدد بدقة كيف يستخدم


لا يجوز حذف كود مستخدم في مستندات مرحلة


يمكن تعطيله بدل الحذف


حسابات الضريبة يجب أن تكون معرفة


ينبغي دعم الضرائب المختلفة بشكل مرن



6.2 Module B — Tax Calculation Engine
هذا هو محرك حساب الضريبة.
المطلوب


احتساب الضريبة على السطر


احتساب الضريبة على الفاتورة


دعم الخصم قبل الضريبة أو بعدها حسب السياسة


التقريب المالي الثابت


دعم البيع والشراء


الخدمة الأساسية
TaxCalculationService
المدخلات


document_type


tax_code


taxable_amount


discount context


المخرجات


tax_amount


tax_breakdown


قواعد الأعمال


الحساب يجب أن يتم مركزيًا في backend


يجب توحيد التقريب عبر النظام


يجب أن تكون النتائج قابلة للتتبع


لا يجوز اختلاف حساب الضريبة بين التقرير والمستند



6.3 Module C — Tax Ledger & Tax Tracking
هذا الموديول يتتبع أثر الضريبة عبر الزمن.
المطلوب


تتبع ضريبة المخرجات من المبيعات


تتبع ضريبة المدخلات من المشتريات


عرض الرصيد الضريبي للفترة


عرض الحركات المرتبطة بكل كود ضريبي


الكيانات


TaxTransaction


TaxSummarySnapshot (اختياري)


الحقول الأساسية لـ TaxTransaction


id


organization_id


tax_code_id


source_type


source_id


document_date


fiscal_period_id


taxable_amount


tax_amount


tax_direction


journal_entry_id


created_at


قواعد الأعمال


كل مستند ضريبي يجب أن يولد أثرًا ضريبيًا واضحًا


يجب الربط بين الضريبة والمستند والقيد


لا يجوز فقدان traceability بين الفاتورة والتقرير الضريبي



6.4 Module D — Tax Reports
هذا موديول تقارير الامتثال الداخلي.
التقارير المطلوبة


Sales Tax Report


Purchase Tax Report


Net Tax Position Report


Tax by Code Report


Tax Audit Trail Report


المخرجات


إجمالي المبيعات الخاضعة


إجمالي ضريبة المخرجات


إجمالي المشتريات الخاضعة


إجمالي ضريبة المدخلات


صافي الضريبة


تفاصيل حسب الفاتورة/الكود


قواعد الأعمال


التقارير تعتمد على المستندات المرحلة فقط


يجب دعم الفلترة بالفترة والفرع والشركة


يجب أن تطابق نتائج التقارير الحسابات المحاسبية



6.5 Module E — Period-End Adjustments
هذا الموديول يدير قيود التسوية.
المطلوب
دعم قيود مثل:


المصروفات المستحقة


الإيرادات المستحقة


المصروفات المقدمة


الإيرادات المؤجلة


تسويات يدوية


تسويات الجرد


تسويات بنكية ختامية


قيود إعادة التصنيف


الكيان


AdjustmentEntry


AdjustmentEntryTemplate (اختياري)


الحقول الأساسية


id


organization_id


adjustment_number


adjustment_date


adjustment_type


description


fiscal_period_id


journal_entry_id


status


created_by


approved_by


created_at


updated_at


قواعد الأعمال


كل تسوية يجب أن ترتبط بقيد محاسبي


لا يجوز اعتماد التسوية دون صلاحيات مناسبة


يجب أن تظهر التسويات بوضوح في تقارير الفترة


يفضّل فصل قيود التسوية عن القيود التشغيلية



6.6 Module F — Closing Checklist Engine
هذا موديول مهم جدًا للحوكمة.
المطلوب
إنشاء checklist قبل الإقفال مثل:


كل القيود المرحلة؟


هل توجد مسودات مفتوحة؟


هل توجد فواتير غير مكتملة؟


هل توجد دفعات غير مخصصة؟


هل توجد حركات بنكية غير مسواة؟


هل الجرد مكتمل؟


هل التسويات أنشئت؟


هل الضريبة راجعت؟


الكيان


ClosingChecklist


ClosingChecklistItem


الحقول الأساسية


id


organization_id


fiscal_period_id


checklist_name


status


generated_at


completed_at


قواعد الأعمال


لا يجوز إقفال الفترة إذا فشلت قواعد حرجة


بعض البنود قد تكون تحذيرًا، وبعضها مانعًا للإقفال


يجب تسجيل من اعتمد الإقفال



6.7 Module G — Period Closing Engine
هذا هو قلب المرحلة.
المطلوب


إغلاق الفترة ماليًا


منع أي ترحيل جديد


قفل المستندات المرتبطة


حفظ snapshot منطقي عند الحاجة


تسجيل الإقفال


الخدمة الأساسية
CloseFiscalPeriodService
المدخلات


fiscal_period_id


actor_id


closing_notes


التحقق


الفترة موجودة ومفتوحة


الـ checklist اجتازت


لا توجد مسودات حرجة


لا توجد حركات غير متوازنة


التسويات المطلوبة منفذة


المخرجات


تغيير حالة الفترة إلى Closed أو Locked


تسجيل عملية الإغلاق


منع الترحيل داخلها


تسجيل Audit Log


قواعد الأعمال


الإقفال عملية رسمية لا رجعة فيها إلا بصلاحية خاصة


إعادة الفتح لا بد أن تكون مسجلة ومبررة


لا يجوز إقفال فترة فيها مشاكل حرجة



6.8 Module H — Reopen Period Governance
هذا الموديول مهم للرقابة.
المطلوب


إعادة فتح فترة مغلقة بصلاحية خاصة


تسجيل السبب


تسجيل المستخدم


تحديد إن كانت الفتح مؤقتًا أو رسميًا


الخدمة الأساسية
ReopenFiscalPeriodService
قواعد الأعمال


لا يجوز إعادة الفتح إلا لصلاحية عليا


يجب تسجيل السبب تفصيليًا


يجب تسجيل كل أثر لاحق حدث بعد إعادة الفتح



6.9 Module I — Closing Entries Engine
هذا الموديول ينفذ قيود الإقفال النهائية.
المطلوب


تجميع حسابات الإيرادات


تجميع حسابات المصروفات


احتساب صافي الربح/الخسارة


إنشاء قيد إقفال


ترحيل الرصيد إلى حساب الأرباح المبقاة أو الحساب المعتمد


الخدمة الأساسية
GenerateClosingEntriesService
القيد النموذجي


إقفال الإيرادات إلى حساب ملخص الدخل


إقفال المصروفات إلى حساب ملخص الدخل


تحويل الصافي إلى الأرباح المبقاة


قواعد الأعمال


يجب أن تنفذ مرة واحدة لكل فترة إلا إذا عكست رسميًا


يجب ربطها بالفترة


يجب أن تظهر بوضوح في السجل



6.10 Module J — Financial Statement Mapping
هذا موديول مهم للتقارير الرسمية.
المطلوب
ربط الحسابات بعناصر القوائم:


قائمة الدخل


المركز المالي


التدفقات النقدية لاحقًا


الكيانات


ReportLine


AccountReportMapping


الحقول الأساسية


id


report_type


line_code


line_name_ar


line_name_en


parent_line_id


sort_order


is_total_line


قواعد الأعمال


كل حساب يجب أن يربط ببند تقرير مناسب


يجب دعم الشجرة في القوائم


لا يجوز إصدار قوائم نهائية من دون mapping صحيح



6.11 Module K — Financial Statements Engine
هذا هو مولد القوائم الرسمية.
المطلوب
إصدار:


Trial Balance


Adjusted Trial Balance


Income Statement


Balance Sheet


General Ledger


Journal Report


Closing Entries Report


الخدمات الأساسية


GenerateTrialBalanceService


GenerateAdjustedTrialBalanceService


GenerateIncomeStatementService


GenerateBalanceSheetService


قواعد الأعمال


يجب أن تعتمد القوائم على القيود المرحلة فقط


يجب دعم:


company


branch


date range


fiscal period




يجب أن تكون القوائم قابلة للمراجعة والتتبع



6.12 Module L — Financial Review & Sign-off
هذا موديول إداري رقابي.
المطلوب


تسجيل مراجعة الفترة


تسجيل المراجع/المدير المالي


تسجيل ملاحظات الإقفال


تسجيل الاعتماد النهائي


الكيان


PeriodSignOff


الحقول الأساسية


id


organization_id


fiscal_period_id


reviewed_by


approved_by


review_notes


approval_notes


signed_off_at


status


قواعد الأعمال


الإقفال النهائي يفضل أن يمر بمستويين: مراجعة ثم اعتماد


التوقيع المالي يجب أن يكون موثقًا



7. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/  tax/    codes/    profiles/    transactions/    reports/  closing/    adjustments/    checklist/    period_closing/    closing_entries/    signoff/  financial_reports/    mappings/    statements/    exports/

مثال تقسيم داخلي
closing/period_closing/  models/    closing_run.py  services/    close_period.py    reopen_period.py    validate_checklist.py  selectors/    closing_queries.py  api/    serializers.py    views.py    urls.py  validators/    close_rules.py  tests/

8. APIs المطلوبة في هذه المرحلة
8.1 Tax Codes / Profiles


POST /api/v1/tax-codes/


GET /api/v1/tax-codes/


GET /api/v1/tax-codes/{id}/


PATCH /api/v1/tax-codes/{id}/


POST /api/v1/tax-profiles/


GET /api/v1/tax-profiles/


8.2 Tax Reports


GET /api/v1/tax-reports/sales/


GET /api/v1/tax-reports/purchases/


GET /api/v1/tax-reports/net-position/


GET /api/v1/tax-reports/by-code/


8.3 Adjustments


POST /api/v1/adjustment-entries/


GET /api/v1/adjustment-entries/


GET /api/v1/adjustment-entries/{id}/


POST /api/v1/adjustment-entries/{id}/post/


8.4 Closing Checklist


POST /api/v1/closing-checklists/generate/


GET /api/v1/closing-checklists/


GET /api/v1/closing-checklists/{id}/


8.5 Period Closing


POST /api/v1/fiscal-periods/{id}/close/


POST /api/v1/fiscal-periods/{id}/reopen/


GET /api/v1/fiscal-periods/{id}/closing-status/


8.6 Closing Entries


POST /api/v1/fiscal-periods/{id}/generate-closing-entries/


GET /api/v1/fiscal-periods/{id}/closing-entries/


8.7 Financial Statements


GET /api/v1/reports/trial-balance/


GET /api/v1/reports/adjusted-trial-balance/


GET /api/v1/reports/income-statement/


GET /api/v1/reports/balance-sheet/


GET /api/v1/reports/general-ledger/


GET /api/v1/reports/journal-report/


8.8 Sign-off


POST /api/v1/fiscal-periods/{id}/review/


POST /api/v1/fiscal-periods/{id}/approve/



9. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — تعريف كود ضريبي


إنشاء كود ضريبي


ربطه بحساب ضريبة مناسب


تفعيله


النتيجة المقبولة:
يمكن استخدامه في البيع والشراء ويظهر أثره في التقارير.

سيناريو 2 — بيع وشراء مع ضريبة


إصدار فاتورة بيع بضريبة


إصدار فاتورة شراء بضريبة


ترحيل العمليتين


استخراج التقرير الضريبي


النتيجة المقبولة:


تظهر ضريبة المخرجات


تظهر ضريبة المدخلات


صافي الضريبة صحيح



سيناريو 3 — إنشاء قيد تسوية


إنشاء Adjustment Entry


ترحيله


عرض أثره في ميزان المراجعة


النتيجة المقبولة:
يظهر الأثر بوضوح ويحسب ضمن الفترة.

سيناريو 4 — تشغيل checklist للإقفال


توليد checklist


مراجعة البنود


معالجة البنود الحرجة


النتيجة المقبولة:
لا يسمح بالإقفال إذا بقيت مشاكل مانعة.

سيناريو 5 — إغلاق فترة


اجتياز checklist


تنفيذ Close Period


محاولة ترحيل قيد جديد داخل الفترة


النتيجة المقبولة:
يتم منع أي ترحيل جديد داخل الفترة المغلقة.

سيناريو 6 — إنشاء قيود الإقفال


إغلاق فترة مالية


توليد closing entries


مراجعة حساب الأرباح والخسائر


النتيجة المقبولة:


تقفل الإيرادات والمصروفات


ينتقل الصافي إلى الحساب المستهدف



سيناريو 7 — إصدار القوائم المالية


استخراج Trial Balance


استخراج Adjusted Trial Balance


استخراج Income Statement


استخراج Balance Sheet


النتيجة المقبولة:
القوائم متوازنة، ومنطقية، وتطابق القيود المرحلة.

10. قواعد الأعمال الملزمة
على مستوى الضرائب


لا يجوز استخدام كود ضريبي غير نشط


يجب أن يكون لكل كود حسابات واضحة


لا يجوز اختلاف الحساب الضريبي بين المستند والتقرير


الضريبة تحتسب بطريقة مركزية موحدة


على مستوى التسويات


كل تسوية يجب أن تكون بقيد محاسبي


لا بد من سبب ووصف واضح


يفضل اعتماد التسويات الحساسة بصلاحية أعلى


على مستوى الإقفال


لا يجوز إغلاق فترة قبل اجتياز checklist


لا يجوز الترحيل في فترة مغلقة


إعادة الفتح عملية استثنائية موثقة


الإقفال يجب أن يسجل بالكامل في Audit Log


على مستوى التقارير المالية


تعتمد على القيود المرحلة فقط


يجب أن تكون القوائم قابلة للتفسير


يجب أن تطابق دفتر الأستاذ وميزان المراجعة



11. قاعدة البيانات المقترحة لهذه المرحلة
11.1 tax_codes


id


organization_id


code


name_ar


name_en


tax_type


rate


applies_to


output_tax_account_id


input_tax_account_id


is_active


created_at


updated_at


11.2 tax_profiles


id


organization_id


name


default_sales_tax_code_id


default_purchase_tax_code_id


is_active


11.3 tax_transactions


id


organization_id


tax_code_id


source_type


source_id


document_date


fiscal_period_id


taxable_amount


tax_amount


tax_direction


journal_entry_id


created_at


11.4 adjustment_entries


id


organization_id


adjustment_number


adjustment_date


adjustment_type


description


fiscal_period_id


journal_entry_id


status


created_by


approved_by


created_at


updated_at


11.5 closing_checklists


id


organization_id


fiscal_period_id


checklist_name


status


generated_at


completed_at


11.6 closing_checklist_items


id


checklist_id


code


name


severity


status


details


resolved_by


resolved_at


11.7 closing_runs


id


organization_id


fiscal_period_id


started_by


completed_by


closing_notes


status


started_at


completed_at


11.8 period_signoffs


id


organization_id


fiscal_period_id


reviewed_by


approved_by


review_notes


approval_notes


signed_off_at


status


11.9 report_lines


id


report_type


line_code


line_name_ar


line_name_en


parent_line_id


sort_order


is_total_line


11.10 account_report_mappings


id


organization_id


account_id


report_line_id


report_type



12. الترتيب التنفيذي داخل Phase 6
Sprint 1


tax codes


tax profiles


tax calculation service


tax tracking


Sprint 2


tax reports


tax audit traceability


validation across sales/purchases


Sprint 3


adjustment entries


end-of-period adjustments


posting rules


Sprint 4


closing checklist


closing validation engine


close/reopen governance


Sprint 5


closing entries engine


retained earnings transfer


period signoff


Sprint 6


financial statement mappings


financial statement engine


official report outputs



13. الاختبارات المطلوبة
Unit Tests


tax calculation logic


tax rounding


tax direction mapping


closing checklist validation


close period preconditions


closing entries generation


statement mapping rules


Integration Tests


sales invoice with tax → tax transaction created


purchase invoice with tax → input tax tracked


adjustment entry → affects adjusted trial balance


closing checklist blocks invalid close


close period blocks new postings


closing entries update retained earnings correctly


Workflow Tests


full monthly close workflow


generate tax reports and compare to ledger


create adjustments then issue final statements


reopen period with approval and audit trace



14. شروط القبول قبل إغلاق Phase 6
Tax


يمكن إنشاء أكواد ضريبية واستخدامها


تتبع ضريبة المخرجات والمدخلات صحيح


التقارير الضريبية تطابق القيود


Adjustments


يمكن إنشاء قيود تسوية وترحيلها


تظهر بوضوح في التقارير


تخضع للصلاحيات المناسبة


Closing


يمكن توليد checklist


الإقفال يفشل عند وجود مشاكل حرجة


الإقفال يمنع الترحيل الجديد


إعادة الفتح موثقة بالكامل


Closing Entries


يمكن توليد قيود الإقفال


تقفل حسابات الدخل بشكل صحيح


ينتقل الصافي إلى الحساب المستهدف


Financial Statements


Trial Balance صحيح


Adjusted Trial Balance صحيح


Income Statement منطقي


Balance Sheet متوازن


النتائج قابلة للمراجعة والتتبع



15. ما الذي يعتبر فشلًا في هذه المرحلة؟
Phase 6 تعتبر غير مكتملة إذا:


اختلفت التقارير الضريبية عن القيود أو المستندات


أمكن إغلاق فترة مع مشاكل حرجة


أمكن الترحيل بعد الإقفال


لم تتولد قيود الإقفال بشكل صحيح


قائمة الدخل أو المركز المالي لا يطابقان الأستاذ العام


إعادة فتح الفترة لا تسجل أثرًا رقابيًا واضحًا



16. الخلاصة التنفيذية
بعد Phase 6 يصبح لديك:


محرك ضريبي


تقارير ضريبية


تسويات نهاية الفترة


إقفال مالي


قيود إقفال


قوائم مالية رسمية


دورة مالية قابلة للمراجعة والاعتماد


وهنا يصبح النظام ليس فقط نظام تشغيل محاسبي، بل نظامًا ماليًا رسميًا.

17. الخطوة التالية المنطقية
بعد اكتمال واختبار Phase 6 بالكامل، المرحلة التالية الطبيعية جدًا هي:
Phase 7 — الذكاء المالي، التدقيق الذكي، التنبيهات، ولوحات الإدارة
وفيها نضيف:


anomaly detection


duplicate detection


fraud/risk flags


smart assistant


executive dashboard


alerts


financial insights


prediction hooks


وهذه المرحلة هي التي ستميز منتجك عن الأنظمة التقليدية.