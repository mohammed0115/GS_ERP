# المتطلبات التقنية لنظام إدارة الموارد البشرية (HRMS) ضمن منظومة GS ERP

## 1. المقدمة

تهدف هذه الوثيقة إلى تحديد المتطلبات التقنية الشاملة لتطوير ودمج نظام إدارة الموارد البشرية (HRMS) كوحدة جديدة ضمن منظومة GS ERP الحالية. سيتناول البحث الجوانب المعمارية، تصميم قواعد البيانات، واجهات برمجة التطبيقات (APIs)، اعتبارات الأمان، قابلية التوسع، ومتطلبات التكامل مع الأنظمة الخارجية، مع التركيز بشكل خاص على الامتثال للوائح المحلية في المملكة العربية السعودية وجمهورية مصر العربية.

## 2. نظرة عامة على موديولات نظام إدارة الموارد البشرية (HRMS)

يتكون نظام إدارة الموارد البشرية الحديث من عدة موديولات أساسية تهدف إلى أتمتة وتبسيط العمليات المتعلقة بالموظفين [2] [7]. تشمل هذه الموديولات:

*   **إدارة معلومات الموظفين (Core HR):** تتضمن بيانات الموظفين الأساسية، الوظائف، الأقسام، الهيكل التنظيمي، وتتبع التغييرات في بيانات الموظفين [7] [9].
*   **إدارة التوظيف والتعيين (Recruitment & Onboarding):** تغطي دورة التوظيف من إنشاء الوظائف الشاغرة، تتبع المتقدمين، إدارة المقابلات، إلى عملية التعيين وإعداد الموظفين الجدد [7] [9].
*   **إدارة الحضور والانصراف (Time & Attendance Management):** تتبع ساعات العمل، الإجازات، الغياب، والعمل الإضافي. يتطلب هذا الموديول تكاملاً مع أجهزة البصمة أو أنظمة تسجيل الدخول والخروج [7] [9].
*   **إدارة الرواتب (Payroll Management):** حساب الرواتب، البدلات، الخصومات، الضرائب، والتأمينات الاجتماعية. يتطلب تكاملاً وثيقاً مع موديول المالية وأنظمة حماية الأجور (WPS) [7] [9].
*   **إدارة الإجازات (Leave Management):** إدارة طلبات الإجازات، الموافقات، وتتبع أرصدة الإجازات للموظفين [7] [9].
*   **إدارة الأداء (Performance Management):** تحديد الأهداف، تقييم الأداء، إدارة الملاحظات، وتخطيط التطوير الوظيفي [7] [8].
*   **إدارة التدريب والتطوير (Training & Development):** تخطيط الدورات التدريبية، تتبع سجلات التدريب، وتقييم فعالية التدريب [7].
*   **إدارة المزايا والتعويضات (Benefits Administration):** إدارة خطط التأمين الصحي، المعاشات التقاعدية، والمزايا الأخرى للموظفين [7].

## 3. المتطلبات المعمارية والتقنية

بناءً على تحليل البنية المعمارية الحالية لنظام GS ERP (الباب الأول من المخطط التقني)، يجب أن يلتزم موديول HRMS بنفس المبادئ المعمارية لضمان التوافق والتكامل السلس [1].

### 3.1. البنية المعمارية

يجب أن يتبع موديول HRMS **البنية متعددة الطبقات (N-tier Architecture)** أو **البنية السحابية (Cloud-native Architecture) مع الميكروسيرفس (Microservices)**، كما هو موضح في المخطط التقني الحالي [1] [4]. هذا يضمن:

*   **قابلية التوسع (Scalability):** القدرة على التعامل مع زيادة عدد الموظفين والبيانات دون التأثير على الأداء.
*   **المرونة (Flexibility):** سهولة التعديل والتطوير المستقبلي للموديول.
*   **فصل الاهتمامات (Separation of Concerns):** فصل واضح بين طبقات العرض، المنطق، والبيانات.

### 3.2. تصميم قواعد البيانات

يجب أن يتبع تصميم قاعدة بيانات HRMS نفس مبادئ تصميم قواعد البيانات الموضحة في المخطط التقني الحالي، مع التركيز على قواعد البيانات العلائقية (Relational Databases) للبيانات الحساسة والمنظمة [3].

**3.2.1. الجداول الأساسية المقترحة:**

| الجدول | الوصف | الحقول الرئيسية المقترحة |
|---|---|---|
| `Employees` | معلومات الموظفين الأساسية | `employee_id (PK)`, `first_name`, `last_name`, `email`, `phone`, `date_of_birth`, `hire_date`, `job_title_id (FK)`, `department_id (FK)`, `manager_id (FK)`, `status` |
| `JobTitles` | مسميات الوظائف | `job_title_id (PK)`, `title_name`, `description` |
| `Departments` | الأقسام | `department_id (PK)`, `department_name`, `location` |
| `Attendance` | سجلات الحضور والانصراف | `attendance_id (PK)`, `employee_id (FK)`, `check_in_time`, `check_out_time`, `status` |
| `Leaves` | طلبات الإجازات | `leave_id (PK)`, `employee_id (FK)`, `leave_type_id (FK)`, `start_date`, `end_date`, `status`, `approver_id (FK)` |
| `LeaveTypes` | أنواع الإجازات | `leave_type_id (PK)`, `type_name`, `max_days` |
| `Payroll` | بيانات الرواتب | `payroll_id (PK)`, `employee_id (FK)`, `pay_period_start`, `pay_period_end`, `gross_salary`, `deductions`, `net_salary`, `status` |
| `Deductions` | أنواع الخصومات | `deduction_id (PK)`, `deduction_name`, `amount_type` |
| `Benefits` | المزايا | `benefit_id (PK)`, `benefit_name`, `description` |
| `EmployeeBenefits` | ربط الموظفين بالمزايا | `employee_benefit_id (PK)`, `employee_id (FK)`, `benefit_id (FK)`, `enrollment_date` |

**3.2.2. مبادئ تصميم قواعد البيانات:**

*   **التطبيع (Normalization):** لتقليل تكرار البيانات وضمان تكاملها [3].
*   **الفهرسة (Indexing):** لتحسين أداء الاستعلامات على الحقول المستخدمة بشكل متكرر [3].
*   **العلاقات (Relationships):** تحديد العلاقات بين الجداول (واحد لواحد، واحد لمتعدد، متعدد لمتعدد) لضمان تكامل البيانات وتسهيل الاستعلامات المعقدة [3].

### 3.3. واجهات برمجة التطبيقات (APIs)

يجب أن يوفر موديول HRMS مجموعة من واجهات برمجة التطبيقات (APIs) المستندة إلى RESTful لتمكين التكامل مع موديولات GS ERP الأخرى (مثل المالية، إدارة المستخدمين والأدوار) ومع الأنظمة الخارجية [7] [8].

**3.3.1. أمثلة على APIs المقترحة:**

*   `POST /employees`: لإنشاء سجل موظف جديد.
*   `GET /employees/{id}`: لاستعراض تفاصيل موظف معين.
*   `PUT /employees/{id}`: لتحديث بيانات موظف.
*   `GET /attendance`: لاستعراض سجلات الحضور والانصراف.
*   `POST /attendance`: لتسجيل دخول/خروج موظف (يمكن أن يتم تلقائياً من أجهزة البصمة).
*   `GET /payroll/{employee_id}`: لاستعراض كشوف رواتب موظف.
*   `POST /payroll/process`: لمعالجة الرواتب لفترة معينة.
*   `GET /leaves`: لاستعراض طلبات الإجازات.
*   `POST /leaves`: لتقديم طلب إجازة جديد.

**3.3.2. معايير تصميم APIs:**

*   **RESTful Principles:** استخدام أفعال HTTP القياسية (GET, POST, PUT, DELETE) والموارد المحددة [7].
*   **التوثيق (Documentation):** توفير توثيق شامل للـ APIs باستخدام أدوات مثل Swagger/OpenAPI [8].
*   **الأمان (Security):** تأمين الـ APIs باستخدام آليات المصادقة (Authentication) والترخيص (Authorization) المناسبة (مثل OAuth 2.0، JWT) [15].

## 4. اعتبارات التكامل

يُعد التكامل السلس مع الموديولات الأخرى والأنظمة الخارجية أمراً بالغ الأهمية لنجاح نظام HRMS.

### 4.1. التكامل مع موديول المالية (Payroll to General Ledger Integration)

يجب أن يتكامل موديول الرواتب في HRMS بشكل وثيق مع موديول المالية الحالي في GS ERP لضمان ترحيل القيود المحاسبية المتعلقة بالرواتب (مثل الرواتب المستحقة، الخصومات، الضرائب، التأمينات الاجتماعية) إلى دفتر الأستاذ العام (General Ledger) بشكل آلي ودقيق [1] [2].

**4.1.1. المتطلبات التقنية للتكامل:**

*   **تحديد الحسابات:** يجب أن يكون هناك آلية لربط أنواع الرواتب والخصومات المختلفة بحسابات محددة في دليل الحسابات (Chart of Accounts) الخاص بموديول المالية [1] [2].
*   **إنشاء قيود يومية آلية:** يجب أن يقوم نظام الرواتب بإنشاء قيود يومية (Journal Entries) تلقائياً بعد معالجة الرواتب، مع ضمان مبدأ القيد المزدوج [1] [2].
*   **واجهات برمجة التطبيقات (APIs):** استخدام APIs الخاصة بموديول المالية (مثل `POST /journals`) لترحيل القيود المحاسبية [1] [2].
*   **التسوية (Reconciliation):** توفير تقارير تسوية لمطابقة إجمالي الرواتب مع القيود المرحّلة إلى دفتر الأستاذ العام [1] [2].

### 4.2. التكامل مع أجهزة البصمة (Biometric Attendance System Integration)

لإدارة الحضور والانصراف، يجب أن يتكامل نظام HRMS مع أجهزة البصمة (مثل أجهزة ZKTeco) لاستيراد بيانات تسجيل الدخول والخروج بشكل آلي [12] [13] [14].

**4.2.1. المتطلبات التقنية للتكامل:**

*   **دعم SDK/API:** يجب أن تدعم أجهزة البصمة واجهات برمجة التطبيقات (APIs) أو حزم تطوير البرامج (SDKs) لتمكين الاتصال واسترجاع البيانات [12] [13].
*   **بروتوكولات الاتصال:** استخدام بروتوكولات اتصال قياسية (مثل TCP/IP) للتواصل مع الأجهزة [12].
*   **معالجة البيانات:** يجب أن يقوم نظام HRMS بمعالجة البيانات المستوردة من أجهزة البصمة (مثل تحويل التوقيتات، تحديد حالات الغياب والتأخير) [12] [13].
*   **المزامنة (Synchronization):** آلية لمزامنة بيانات الموظفين بين نظام HRMS وأجهزة البصمة (مثل إضافة موظف جديد، تحديث بيانات موظف) [12].

### 4.3. الامتثال لنظام حماية الأجور (WPS) في السعودية ومصر

يُعد الامتثال لنظام حماية الأجور (WPS) إلزامياً في كل من المملكة العربية السعودية وجمهورية مصر العربية. يتطلب ذلك إعداد ملفات رواتب بصيغ محددة وتقديمها للبنوك أو الجهات الحكومية [4] [5] [6] [7] [8] [9] [10] [11].

**4.3.1. المتطلبات التقنية لنظام حماية الأجور (WPS) في السعودية:**

*   **صيغة الملف:** ملف نصي (TXT) أو CSV بفاصلة تبويب (TAB-delimited) [4] [5].
*   **هيكل الملف:** يتكون الملف من رأس (Header) وسجلات رواتب (Salary Records) لكل موظف [4] [5].
*   **البيانات المطلوبة:** تتضمن رقم هوية الموظف، اسم الموظف، رقم الحساب البنكي، البنك، الراتب الأساسي، البدلات، الخصومات، وصافي الراتب [4] [5].
*   **التحقق من الصحة (Validation):** يجب أن يقوم النظام بالتحقق من صحة البيانات قبل إنشاء ملف WPS لضمان الامتثال للمواصفات [4] [5].

**4.3.2. المتطلبات التقنية لنظام حماية الأجور (WPS) في مصر:**

*   **صيغة الملف:** تختلف الصيغة المطلوبة حسب البنك، ولكن غالباً ما تكون ملفات CSV أو TXT [7] [8] [9].
*   **البيانات المطلوبة:** تتضمن بيانات الموظف، رقم الحساب البنكي، البنك، الراتب الأساسي، البدلات، الخصومات، وصافي الراتب، بالإضافة إلى تفاصيل التأمينات الاجتماعية والضرائب [7] [8] [9].
*   **الامتثال لقانون العمل المصري:** يجب أن يضمن النظام الامتثال لقانون العمل رقم 12 لسنة 2003، بما في ذلك حساب التأمينات الاجتماعية والضرائب بدقة [7] [8] [9].

## 5. اعتبارات الأمان

يجب أن يلتزم موديول HRMS بأعلى معايير الأمان لحماية بيانات الموظفين الحساسة [15].

*   **المصادقة والترخيص (Authentication & Authorization):** استخدام نظام إدارة المستخدمين والأدوار الحالي في GS ERP لتحديد صلاحيات الوصول لكل مستخدم [15].
*   **تشفير البيانات (Data Encryption):** تشفير البيانات الحساسة (مثل الرواتب، المعلومات الشخصية) سواء كانت مخزنة (Encryption at Rest) أو أثناء النقل (Encryption in Transit) [15].
*   **تدقيق السجلات (Audit Trails):** تسجيل جميع الأنشطة التي تتم على بيانات الموظفين لأغراض التدقيق والامتثال [15].
*   **إدارة الثغرات الأمنية (Vulnerability Management):** إجراء اختبارات أمان منتظمة وتحديث المكونات البرمجية [15].

## 6. قابلية التوسع والأداء

يجب تصميم موديول HRMS ليكون قابلاً للتوسع أفقياً وعمودياً، مع تحسين أداء قواعد البيانات والتطبيقات لضمان استجابة سريعة حتى مع زيادة حجم البيانات وعدد المستخدمين [1] [4].

*   **التوسع الأفقي (Horizontal Scaling):** دعم توزيع الحمل على عدة خوادم (Load Balancing) وقواعد بيانات موزعة (Distributed Databases) [4].
*   **تحسين أداء قواعد البيانات:** استخدام تقنيات تحسين الاستعلامات (Query Optimization) والتخزين المؤقت (Caching) [4].
*   **تحسين الكود (Code Optimization):** كتابة كود فعال ومُحسّن لتقليل استهلاك الموارد [4].

## 7. الخلاصة

يتطلب دمج نظام إدارة الموارد البشرية (HRMS) ضمن منظومة GS ERP تخطيطاً دقيقاً والتزاماً بالمتطلبات التقنية والمعمارية الحالية للنظام. من خلال اتباع المبادئ الموضحة في هذه الوثيقة، يمكن بناء نظام HRMS قوي، آمن، قابل للتوسع، ومتكامل يلبي احتياجات الشركة ويدعم الامتثال للوائح المحلية.

## 8. المراجع

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] A Comprehensive Guide to the ERP HR Module - NetSuite. (2025, December 4). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-hr-module.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] Wages Protection System - Ministry of Human Resources and Social Development. (n.d.). Retrieved from https://www.hrsd.gov.sa/sites/default/files/2017-06/WPS%20Wages%20File%20Technical%20Specification.pdf
[6] ERPNext Customization for UAE and KSA Compliance - Clefincode. (2025, May 29). Retrieved from https://clefincode.com/blog/global-digital-vibes/en/erpnext-customization-for-uae-and-ksa-compliance
[7] The 16 most common HRMS modules & features - HRMS World. (2026, March 24). Retrieved from https://www.hrmsworld.com/16-most-common-hrms-modules.html
[8] 5 Must-Have Features in a Modern HRMS: What the Best ... - Medium. (n.d.). Retrieved from https://medium.com/@meethrhub/5-must-have-features-in-a-modern-hrms-what-the-best-workplaces-dont-compromise-on-54c1c0365587
[9] HRMS Modules & Features Guide for Modern Businesses - Weekmate. (2025, December 29). Retrieved from https://weekmate.in/blog/common-hrms-modules-features-guide-for-modern-businesses/
[10] GOSI & WPS Compliance Saudi Arabia: Payroll Guide 2026 - Infura Group. (n.d.). Retrieved from https://infura-group.com/saudi-gosi-wps-payroll-compliance-guide/
[11] Egypt Payroll 2026: Social Insurance Compliance - MaherCF. (n.d.). Retrieved from https://mahercf.com/en/egypt-payroll-2026-social-insurance-compliance
[12] Integrated Biometric Attendance and HRMS - Spintly. (n.d.). Retrieved from https://spintly.com/blog/integrated-biometric-attendance-and-hrms-the-sync-you-didnt-know-you-needed/
[13] Your Biometric Device Must Be Integrated with Your HRM ... - LinkedIn. (n.d.). Retrieved from https://www.linkedin.com/pulse/your-biometric-device-must-integrated-hrm-software-n1t4f
[14] Biometric Device Integration with HRMS - Open HRMS. (n.d.). Retrieved from https://www.openhrms.com/open-hrms-book/biometric-device-integrations/
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
