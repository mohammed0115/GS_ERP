Phase 7 — الذكاء المالي، التدقيق الذكي، التنبيهات، ولوحات الإدارة
Financial Intelligence, Smart Audit, Alerts & Executive Dashboards
1. اسم المرحلة
Phase 7: AI Finance Layer, Audit Intelligence & Executive Experience
2. الهدف من المرحلة
إضافة طبقة ذكاء فوق النظام المحاسبي والتشغيلي المكتمل، بحيث يصبح النظام قادرًا على:


كشف الشذوذ


رصد المخاطر


كشف التكرار


التنبؤ بالمشكلات


تنبيه الإدارة


توليد ملخصات ذكية


الإجابة على الأسئلة المالية


دعم المدقق والمحاسب والمدير المالي بذكاء فعلي


هذه المرحلة لا تستبدل القواعد المحاسبية، بل تبني فوقها.

3. لماذا هذه المرحلة مهمة؟
لأن معظم الأنظمة المحاسبية التقليدية تتوقف عند:


إدخال العمليات


استخراج التقارير


لكن القيمة الأكبر اليوم تكون في:


ماذا يعني هذا الرقم؟


أين الخطر؟


ما الشذوذ؟


من العميل عالي المخاطر؟


ما المورد غير الطبيعي؟


لماذا ارتفع المصروف؟


ما الذي يجب أن أراجعه قبل نهاية الشهر؟


وهذه بالضبط هي قيمة Phase 7.

4. حدود المرحلة
داخل النطاق


anomaly detection


duplicate detection


suspicious patterns


risk scoring


alerts engine


smart audit cases


executive dashboard


KPI dashboard


financial assistant


narrative insights


report annotations


audit trail intelligence


review workflows for findings


خارج النطاق


Auto-booking without controls


Autonomous finance agent يتصرف وحده


Full ML training pipeline production-scale


External market forecasting


Credit bureau integrations


Regulatory filing automation الكامل


Voice assistant


Generative workflows تغيّر البيانات مباشرة دون اعتماد



5. المخرجات النهائية المطلوبة من Phase 7
في نهاية هذه المرحلة يجب أن يكون النظام قادرًا على:


اكتشاف فواتير مكررة أو شبه مكررة


كشف عمليات شاذة في المبيعات أو المشتريات أو المصروفات


إعطاء درجة مخاطر لكل مستند أو طرف


إنشاء حالات تدقيق Audit Cases


إطلاق تنبيهات عند تجاوز قواعد مالية


عرض لوحة تنفيذية ذكية للإدارة


عرض مؤشرات رئيسية حية


إنشاء ملخصات ذكية للفترة


تمكين المساعد الذكي من الإجابة على الأسئلة المالية


تفسير بعض الانحرافات بناءً على البيانات


دعم المحاسب والمدير المالي والمدقق في اتخاذ القرار



6. المبدأ المعماري الحاكم لهذه المرحلة
الذكاء هنا طبقة مساعدة، لا طبقة حاكمة.
يعني:


AI لا يغير القيود تلقائيًا


AI لا يغلق الفترات


AI لا يعتمد مستندات


AI لا يتجاوز صلاحيات النظام


بل:


يكتشف


يفسر


ينبه


يقترح


يساعد


يرتب الأولويات



7. الموديولات التنفيذية داخل Phase 7
7.1 Module A — Anomaly Detection Engine
هذا هو المحرك الذي يبحث عن العمليات غير المعتادة.
المطلوب
كشف أنماط مثل:


فاتورة بقيمة غير معتادة مقارنة بالتاريخ


مصروف مرتفع جدًا


مورد لم يكن نشطًا ثم ظهرت له حركة كبيرة


عميل بخصومات غير مألوفة


عمليات خارج النمط الزمني المعتاد


تغييرات كبيرة في التكلفة أو الأسعار


الكيان


AnomalyCase


الحقول الأساسية


id


organization_id


source_type


source_id


anomaly_type


severity


score


title


description


evidence_json


status


detected_at


assigned_to


resolved_at


resolution_notes


أنواع الشذوذ المقترحة


Amount Outlier


Frequency Outlier


Timing Outlier


Behavioral Change


Threshold Breach


Pattern Mismatch


قواعد الأعمال


لا يجوز اعتبار كل شذوذ احتيالًا


يجب تقديم evidence واضحة


يجب أن يكون لكل شذوذ مستوى خطورة


يجب أن تكون الحالات قابلة للمراجعة والإغلاق



7.2 Module B — Duplicate Detection Engine
هذا مهم جدًا خصوصًا في الفواتير والمدفوعات.
المطلوب
كشف:


فواتير مكررة


دفعات مكررة


مورد/عميل مكرر


مستندات متشابهة جدًا


أمثلة معايير الكشف


نفس الرقم المرجعي


نفس المورد/العميل


نفس التاريخ أو تاريخ قريب


نفس المبلغ


تشابه في الوصف


تشابه مرتفع في البيانات


الكيان


DuplicateMatch


الحقول الأساسية


id


organization_id


entity_type


left_entity_id


right_entity_id


similarity_score


duplicate_reason


severity


status


created_at


reviewed_by


reviewed_at


قواعد الأعمال


التطابق المحتمل لا يعني تأكيدًا نهائيًا


يجب أن يسمح للمراجع بتأكيد أو رفض الحالة


يجب الاحتفاظ بسجل قرار المراجع



7.3 Module C — Risk Scoring Engine
هذا الموديول يعطي درجة مخاطر للعمليات أو الأطراف.
المطلوب
إعطاء score لعدة كيانات:


Sales Invoice


Purchase Invoice


Customer


Vendor


Treasury Transaction


Inventory Adjustment


عوامل المخاطر الممكنة


قيمة عالية


تكرار غير معتاد


طرف جديد أو غير نشط سابقًا


خصومات غير منطقية


حركة قرب الإقفال


تعديل بعد اعتماد


تعدد العكس أو الإلغاء


فروقات جرد


تأخر سداد


اعتماد مفرط على عميل واحد


الكيان


RiskScore


الحقول الأساسية


id


organization_id


entity_type


entity_id


score


risk_level


contributing_factors_json


calculated_at


مستويات المخاطر


Low


Medium


High


Critical


قواعد الأعمال


score يجب أن يكون قابلًا للتفسير


لا نعتمد black box غير مفهومة


يجب إظهار العوامل المؤثرة في النتيجة



7.4 Module D — Smart Audit Case Management
هذا الموديول ينظم نتائج الذكاء والتدقيق بدل أن تبقى مجرد إشارات.
المطلوب


إنشاء Audit Case


ربطها بمستند أو أكثر


تعيينها لمراجع


تغيير حالتها


تسجيل نتيجة المراجعة


الكيان


AuditCase


الحقول الأساسية


id


organization_id


case_number


source_type


source_id


case_type


severity


status


opened_at


assigned_to


review_notes


outcome


closed_at


الحالات


Open


Under Review


Escalated


Confirmed


Dismissed


Closed


قواعد الأعمال


كل حالة يجب أن تكون قابلة للمتابعة


يجب أن يكون هناك أثر لمراجعة كل حالة


يمكن أن تنشأ الحالة من:


anomaly


duplicate


tax mismatch


unusual adjustment


suspicious payment





7.5 Module E — Alerts Engine
هذا هو محرك التنبيهات اللحظية والدورية.
المطلوب
إطلاق تنبيهات عند تحقق شروط مثل:


تجاوز حد ائتماني


زيادة الذمم المتأخرة


انخفاض السيولة


وجود فواتير عالية المخاطر


فروقات جرد كبيرة


حركات بنكية غير مسواة لفترة طويلة


ضرائب غير متسقة


عمليات قرب الإقفال تحتاج مراجعة


الكيان


AlertRule


AlertEvent


الحقول الأساسية لـ AlertRule


id


organization_id


code


name


alert_type


condition_json


severity


is_active


target_role


الحقول الأساسية لـ AlertEvent


id


organization_id


alert_rule_id


source_type


source_id


message


severity


status


triggered_at


acknowledged_by


acknowledged_at


قواعد الأعمال


التنبيه لا يجب أن يكون مزعجًا بلا قيمة


يجب تصنيف التنبيه حسب الشدة


يجب دعم الإقرار أو الإغلاق أو التصعيد



7.6 Module F — Executive Dashboard
هذا موديول الإدارة العليا.
المطلوب
عرض لوحة تنفيذية تشمل:


الإيرادات


المصروفات


الربحية


الذمم المدينة


الذمم الدائنة


السيولة


أعلى العملاء


أعلى الموردين


البنود عالية المخاطر


التنبيهات المفتوحة


نظرة سريعة على الضرائب


اتجاهات الأداء عبر الزمن


مؤشرات أساسية مقترحة


Revenue This Month


Expenses This Month


Net Profit


Cash Position


Receivables Outstanding


Payables Outstanding


Inventory Value


High Risk Cases


Overdue Invoices


Unreconciled Bank Items


قواعد الأعمال


يجب أن تكون الأرقام ناتجة من مصادر رسمية داخل النظام


يجب أن يكون لكل KPI تعريف واضح


يجب دعم الفلترة بالشركة والفترة والفرع



7.7 Module G — Operational Finance Dashboard
هذا موديول للمحاسب والمدير المالي.
المطلوب
عرض:


فواتير تنتظر مراجعة


قيود معكوسة


حركات عالية المخاطر


عملاء متأخرون


موردون يحتاجون دفعًا


فروقات جرد


بنوك غير مسواة


قيود تسوية مفتوحة


الهدف
إعطاء لوحة عمل يومية عملية، لا مجرد مؤشرات عامة.

7.8 Module H — Financial Assistant
هذا هو المساعد الذكي الذي يجيب على الأسئلة المالية.
المطلوب
دعم أسئلة مثل:


ما سبب انخفاض الربح هذا الشهر؟


من أكثر العملاء تأخرًا في السداد؟


ما أكبر المصروفات خلال آخر 30 يومًا؟


هل توجد فواتير مكررة محتملة؟


ما البنود عالية المخاطر الآن؟


كيف تغيرت السيولة مقارنة بالشهر الماضي؟


ما الموردون الذين زادت فواتيرهم بشكل غير طبيعي؟


المبدأ الصحيح
المساعد لا يخترع أرقامًا، بل:


يسحب البيانات من مصادر معتمدة


يجمعها


يلخصها


يشرحها


يذكر حدود الاستنتاج إن وجدت


المكونات


Query Intent Layer


Metrics Retrieval Layer


Financial Explanation Layer


Citation/Trace Layer داخلي


قواعد الأعمال


يجب أن يعتمد على بيانات النظام فقط


يجب أن يكون كل جواب قابلًا للتتبع


لا يجوز للمساعد تنفيذ تعديل مالي مباشر


يجب أن يوضح متى يكون الجواب “تحليلًا” لا “حقيقة محاسبية مباشرة”



7.9 Module I — Narrative Insights Engine
هذا الموديول يولد ملخصات نصية ذكية.
المطلوب
إنتاج نصوص مثل:


ملخص الأداء الشهري


أسباب تغير الربحية


ملاحظات على الذمم


ملاحظات على السيولة


ملاحظات على المخاطر


تنبيهات على الشذوذ


أمثلة مخرجات


ارتفعت المصروفات التشغيلية 18% مقارنة بالشهر السابق


تركزت 42% من المبيعات في عميلين فقط


توجد 7 فواتير شراء عالية القيمة تم إصدارها آخر ثلاثة أيام من الفترة


ارتفع المخزون الراكد في مستودع معين


قواعد الأعمال


النص يجب أن يبنى على أرقام فعلية


لا يجوز توليد استنتاجات لا يدعمها الدليل


يجب ضبط النبرة لتكون مهنية وليست مبالغًا فيها



7.10 Module J — Financial KPI Engine
هذا الموديول يجمع المؤشرات ويفسرها.
المطلوب
احتساب مؤشرات مثل:


Gross Margin


Net Margin


Receivables Turnover


Days Sales Outstanding


Days Payable Outstanding


Current Ratio


Quick Ratio


Cash Conversion Indicators


Inventory Turnover


Collection Efficiency


الكيان


KPIValue


الحقول الأساسية


id


organization_id


kpi_code


period_start


period_end


value


comparison_value


trend_direction


calculated_at


قواعد الأعمال


كل KPI له formula واضحة


يجب توحيد تعريفات المؤشرات


يجب دعم comparison with previous period



7.11 Module K — Review Workbench
هذا موديول مخصص للمراجع والمدقق.
المطلوب
واجهة عمل موحدة تعرض:


anomalies


duplicates


high-risk documents


pending audit cases


unresolved alerts


suspicious reversals


end-of-period unusual activity


الهدف
تحويل الذكاء إلى workflow يمكن تشغيله داخل الفريق المالي.

7.12 Module L — Explainability Layer
هذه طبقة مهمة جدًا للثقة.
المطلوب
لكل:


score


alert


anomaly


insight


يجب عرض:


لماذا ظهر؟


ما البيانات المستخدمة؟


ما القاعدة أو المؤشر الذي شغّله؟


ما المستندات المرتبطة؟


قواعد الأعمال


لا يجوز تقديم “نتيجة ذكية” بلا تفسير


قابلية التفسير أساسية أكثر من تعقيد النموذج



8. الهيكل المعماري داخل الكود
التقسيم المقترح
apps/  intelligence/    anomalies/    duplicates/    risk_scoring/    audit_cases/    alerts/    insights/    kpis/    assistant/    dashboards/    review_workbench/    explainability/

مثال تقسيم داخلي
intelligence/anomalies/  models/    anomaly_case.py  services/    detect_amount_outliers.py    detect_timing_outliers.py    create_anomaly_case.py  selectors/    anomaly_queries.py  api/    serializers.py    views.py    urls.py  tests/

9. APIs المطلوبة في هذه المرحلة
9.1 Anomalies


GET /api/v1/anomalies/


GET /api/v1/anomalies/{id}/


POST /api/v1/anomalies/{id}/assign/


POST /api/v1/anomalies/{id}/resolve/


9.2 Duplicates


GET /api/v1/duplicate-matches/


GET /api/v1/duplicate-matches/{id}/


POST /api/v1/duplicate-matches/{id}/confirm/


POST /api/v1/duplicate-matches/{id}/dismiss/


9.3 Risk Scores


GET /api/v1/risk-scores/


GET /api/v1/risk-scores/{id}/


9.4 Audit Cases


POST /api/v1/audit-cases/


GET /api/v1/audit-cases/


GET /api/v1/audit-cases/{id}/


POST /api/v1/audit-cases/{id}/assign/


POST /api/v1/audit-cases/{id}/close/


9.5 Alerts


GET /api/v1/alerts/


GET /api/v1/alerts/{id}/


POST /api/v1/alerts/{id}/acknowledge/


POST /api/v1/alerts/{id}/dismiss/


9.6 Dashboards


GET /api/v1/dashboards/executive/


GET /api/v1/dashboards/finance-operations/


GET /api/v1/dashboards/risk-overview/


9.7 Assistant


POST /api/v1/assistant/financial-query/


9.8 Insights / KPI


GET /api/v1/insights/monthly-summary/


GET /api/v1/insights/risk-summary/


GET /api/v1/kpis/


9.9 Review Workbench


GET /api/v1/review-workbench/



10. السيناريوهات الأساسية التي يجب أن تعمل
سيناريو 1 — كشف فاتورة مكررة


تسجيل فاتورتين متشابهتين جدًا


تشغيل duplicate detection


مراجعة النتيجة


النتيجة المقبولة:


تظهر حالة duplicate محتملة


توضح أسباب التشابه


يمكن للمراجع تأكيدها أو رفضها



سيناريو 2 — كشف شذوذ مالي


إنشاء فاتورة شراء بمبلغ غير معتاد جدًا


تشغيل anomaly detection


عرض الحالة في workbench


النتيجة المقبولة:


تنشأ anomaly case


تظهر درجة الخطورة


يظهر الدليل الداعم



سيناريو 3 — تنبيه حد ائتماني


عميل يتجاوز الحد الائتماني


يصدر النظام alert


تظهر في dashboard وفي قائمة التنبيهات


النتيجة المقبولة:
يمكن تتبع التنبيه وإقراره أو تصعيده.

سيناريو 4 — سؤال للمساعد الذكي


يسأل المستخدم: لماذا انخفض الربح هذا الشهر؟


المساعد يجلب البيانات


يولد الإجابة


النتيجة المقبولة:


إجابة مالية مفهومة


مدعومة بعوامل واضحة


لا تحتوي ادعاءات غير مدعومة



سيناريو 5 — ملخص شهري ذكي


نهاية الشهر


النظام يولد monthly insight


المدير يراه على dashboard


النتيجة المقبولة:


النص مبني على أرقام حقيقية


يذكر الاتجاهات المهمة


يشير إلى المخاطر أو الشذوذات



سيناريو 6 — Workbench للمراجع


المراجع يفتح review workbench


يرى:


حالات مفتوحة


duplicates


anomalies


alerts




يبدأ المراجعة


النتيجة المقبولة:
يستطيع إدارة الأولويات بدل التنقل بين تقارير متفرقة.

11. قواعد الأعمال الملزمة
على مستوى الذكاء


الذكاء لا يعدّل البيانات المحاسبية مباشرة


الذكاء لا يعتمد المستندات


الذكاء لا يغلق الفترات


الذكاء لا يعطي نتيجة بلا تفسير


على مستوى الحالات


كل anomaly أو duplicate أو risk flag يجب أن يكون قابلاً للمراجعة


لا يجوز حذف الحالات الحساسة بلا trace


يجب تسجيل قرارات المراجع


على مستوى المساعد


المساعد يعتمد على بيانات النظام فقط


يجب أن يفرق بين fact و inference


لا يجوز أن يختلق أرقامًا


يجب أن يكون قابلًا للتتبع داخليًا


على مستوى dashboards


الأرقام يجب أن تأتي من services موحدة


يجب منع تضارب الأرقام بين dashboard والتقارير الرسمية



12. قاعدة البيانات المقترحة لهذه المرحلة
12.1 anomaly_cases


id


organization_id


source_type


source_id


anomaly_type


severity


score


title


description


evidence_json


status


detected_at


assigned_to


resolved_at


resolution_notes


12.2 duplicate_matches


id


organization_id


entity_type


left_entity_id


right_entity_id


similarity_score


duplicate_reason


severity


status


created_at


reviewed_by


reviewed_at


12.3 risk_scores


id


organization_id


entity_type


entity_id


score


risk_level


contributing_factors_json


calculated_at


12.4 audit_cases


id


organization_id


case_number


source_type


source_id


case_type


severity


status


opened_at


assigned_to


review_notes


outcome


closed_at


12.5 alert_rules


id


organization_id


code


name


alert_type


condition_json


severity


is_active


target_role


12.6 alert_events


id


organization_id


alert_rule_id


source_type


source_id


message


severity


status


triggered_at


acknowledged_by


acknowledged_at


12.7 kpi_values


id


organization_id


kpi_code


period_start


period_end


value


comparison_value


trend_direction


calculated_at


12.8 insight_snapshots


id


organization_id


insight_type


title


content


generated_for_period


generated_at


12.9 assistant_queries


id


organization_id


user_id


query_text


response_text


response_type


created_at



13. الترتيب التنفيذي داخل Phase 7
Sprint 1


KPI engine


executive dashboard


finance operations dashboard


Sprint 2


anomaly detection basics


duplicate detection basics


explainability layer


Sprint 3


risk scoring


alert rules


alert events


risk overview dashboard


Sprint 4


audit cases


review workbench


assignment and resolution workflows


Sprint 5


assistant query layer


narrative insights


monthly summaries


financial explanations


Sprint 6


hardening


tuning false positives


permissions


auditability


production review



14. الاختبارات المطلوبة
Unit Tests


duplicate score calculation


anomaly rule thresholds


risk scoring logic


KPI formula correctness


alert triggering conditions


insight generation validation


Integration Tests


invoice created → risk score calculated


duplicate documents → duplicate case generated


threshold breach → alert generated


closing month → insight summary generated


dashboard metrics match financial reports


Workflow Tests


reviewer receives anomaly → investigates → closes case


CFO opens dashboard → sees accurate KPIs


user asks assistant → gets grounded response


alert acknowledged → tracked properly



15. شروط القبول قبل إغلاق Phase 7
Intelligence


النظام يكتشف على الأقل مجموعة واضحة من anomalies


النظام يكتشف duplicates بشكل قابل للمراجعة


score المخاطر يظهر مع تفسير


Alerts


التنبيهات تعمل وفق قواعد واضحة


يمكن إقرارها أو إغلاقها أو تصعيدها


لا يوجد spam غير مفيد


Dashboards


executive dashboard دقيق ومفيد


finance operations dashboard عملي


الأرقام تطابق التقارير المالية الرسمية


Assistant


يجيب على الأسئلة المالية الشائعة


يعتمد على البيانات الفعلية


لا يختلق أرقامًا


يقدّم تحليلًا مفهومًا


Audit Workbench


يمكن للمراجع إدارة الحالات بسهولة


كل قرار موثق


traceability كاملة



16. ما الذي يعتبر فشلًا في هذه المرحلة؟
Phase 7 تعتبر غير مكتملة إذا:


ظهرت نتائج ذكية بلا تفسير


dashboard لا يطابق التقارير الرسمية


assistant يختلق أرقامًا أو استنتاجات غير مدعومة


anomaly engine ينتج ضوضاء بلا قيمة


لا يمكن للمراجع تتبع أصل الحالة


alerts مزعجة وغير قابلة للإدارة



17. الخلاصة التنفيذية
بعد Phase 7 يصبح لديك:


نظام محاسبي متكامل


تشغيل مالي وتشغيلي كامل


ضرائب وإقفال وتقارير رسمية


ذكاء مالي


تدقيق ذكي


تنبيهات


لوحات تنفيذية


مساعد مالي ذكي


Workbench للمراجعة


وهنا يتحول المنتج من:
Accounting System
إلى:
Smart Financial Operations & Audit Platform
وهذا هو المكان الذي يبدأ فيه التميز الحقيقي عن أغلب الأنظمة التقليدية.

18. الترتيب النهائي الذي أصبح عندك
أنت الآن تملك هيكلًا منطقيًا كاملًا للمشروع:


Phase 0 — التأسيس المعماري


Phase 1 — النواة المحاسبية


Phase 2 — المبيعات والتحصيل


Phase 3 — المشتريات والدفع


Phase 4 — الخزينة والبنوك


Phase 5 — المخزون والمستودعات


Phase 6 — الضرائب والإقفال والتقارير الرسمية


Phase 7 — الذكاء المالي والتدقيق الذكي ولوحات الإدارة



19. ماذا ينقص بعد هذه المراحل؟
بعد اكتمال هذه المراحل، تبقى طبقات داعمة مهمة جدًا، مثل:


الهوية والأمان المؤسسي المتقدم


التكاملات الخارجية


إدارة الوثائق والمرفقات


Workflow approvals


multi-company consolidation


export/import layer


deployment, observability, backup, DR


mobile responsiveness and product polish


pricing, billing, tenant plans


لكن جوهر النظام المحاسبي الذكي نفسه أصبح واضحًا ومكتملًا معماريًا.
الخطوة التالية الأفضل الآن هي أن أجمع لك المراحل 0 إلى 7 كلها في Master Execution Blueprint واحد مرتب جدًا بحيث يصبح هو المرجع الرسمي للتنفيذ.