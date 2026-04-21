# الباب الأول: البنية الأساسية لنظام ERP والبنية التحتية (Core ERP Architecture and Infrastructure)

## 1.1. نماذج البنية المعمارية لأنظمة ERP

![مخطط البنية الأساسية لنظام ERP](Chapter_01_Core_ERP_Architecture_and_Infrastructure.png)

تُعد البنية المعمارية (Architecture) حجر الزاوية في تصميم أي نظام برمجي معقد، وأنظمة تخطيط موارد المؤسسات (ERP) ليست استثناءً. تحدد البنية كيفية تنظيم المكونات المختلفة للنظام، وكيفية تفاعلها مع بعضها البعض، ومع المستخدمين، ومع الأنظمة الخارجية. تطورت نماذج البنية المعمارية لأنظمة ERP على مر السنين لتلبية المتطلبات المتزايدة من حيث الأداء، قابلية التوسع، والمرونة [1] [3].

### 1.1.1. البنية ثنائية الطبقات (Two-tier Architecture)

في هذا النموذج، يتم تقسيم النظام إلى طبقتين رئيسيتين: طبقة العميل (Client Tier) وطبقة الخادم (Server Tier). تتولى طبقة العميل مسؤولية واجهة المستخدم ومعالجة المنطق الأساسي، بينما تتولى طبقة الخادم مسؤولية تخزين البيانات وإدارة قواعد البيانات. هذا النموذج بسيط وسهل التنفيذ للأنظمة الصغيرة، ولكنه يفتقر إلى قابلية التوسع والمرونة اللازمة للأنظمة الكبيرة والمعقدة [1].

### 1.1.2. البنية ثلاثية الطبقات (Three-tier Architecture)

يُعد هذا النموذج الأكثر شيوعاً في أنظمة ERP الحديثة. يتم تقسيم النظام إلى ثلاث طبقات متميزة: طبقة العرض (Presentation Tier)، طبقة المنطق (Application Tier)، وطبقة البيانات (Data Tier). تتولى طبقة العرض مسؤولية واجهة المستخدم، بينما تتولى طبقة المنطق معالجة قواعد العمل والمنطق البرمجي، وتتولى طبقة البيانات تخزين وإدارة قواعد البيانات. يوفر هذا النموذج قابلية أفضل للتوسع، ومرونة أكبر في التطوير والصيانة، وفصلاً واضحاً للمسؤوليات بين الطبقات [1] [3].

### 1.1.3. البنية متعددة الطبقات (N-tier Architecture)

تُعد البنية متعددة الطبقات امتداداً للبنية ثلاثية الطبقات، حيث يتم تقسيم طبقة المنطق (Application Tier) إلى عدة طبقات فرعية، مثل طبقة الخدمات (Services Layer)، طبقة قواعد العمل (Business Logic Layer)، وطبقة الوصول إلى البيانات (Data Access Layer). يتيح هذا النموذج مرونة أكبر في تصميم النظام، وقابلية عالية للتوسع، وإمكانية إعادة استخدام المكونات، مما يجعله مناسباً للأنظمة الكبيرة والمعقدة التي تتطلب أداءً عالياً ومرونة في التغيير [4].

### 1.1.4. البنية السحابية (Cloud-native Architecture) والميكروسيرفس (Microservices)

مع تزايد الاعتماد على الحوسبة السحابية، ظهرت البنية السحابية كنموذج حديث لتصميم أنظمة ERP. تعتمد هذه البنية على استخدام الخدمات السحابية (مثل AWS, Azure, Google Cloud) لتوفير البنية التحتية، وتستخدم مفهوم الميكروسيرفس (Microservices) لتقسيم النظام إلى خدمات صغيرة ومستقلة. يتميز هذا النموذج بقابلية عالية للتوسع، ومرونة في التطوير والنشر، ومقاومة للأخطاء، مما يجعله مثالياً للشركات التي تتطلب سرعة في الابتكار والتكيف مع المتغيرات [5].

## 1.2. تصميم قواعد البيانات لأنظمة ERP

تُعد قاعدة البيانات (Database) هي القلب النابض لأي نظام ERP، حيث تخزن جميع البيانات الحيوية للشركة. يجب أن يكون تصميم قاعدة البيانات قوياً، قابلاً للتوسع، وموثوقاً لضمان دقة البيانات وتوفرها [3].

### 1.2.1. اختيار نوع قاعدة البيانات (Relational vs. NoSQL)

*   **قواعد البيانات العلائقية (Relational Databases):** مثل MySQL, PostgreSQL, Oracle, SQL Server. تُعد الخيار التقليدي لأنظمة ERP نظراً لقدرتها على التعامل مع البيانات المنظمة، ودعمها للمعاملات (ACID properties)، وقدرتها على فرض تكامل البيانات من خلال العلاقات والجداول. تُفضل للبيانات المالية، المخزنية، وبيانات العملاء والموردين التي تتطلب دقة عالية وتكامل [3].
*   **قواعد البيانات غير العلائقية (NoSQL Databases):** مثل MongoDB, Cassandra, Redis. تُستخدم للتعامل مع البيانات غير المنظمة أو شبه المنظمة، وتتميز بقابلية عالية للتوسع الأفقي والأداء العالي في بعض السيناريوهات. يمكن استخدامها لتخزين بيانات السجلات (Logs)، بيانات المستخدمين غير الحساسة، أو البيانات التي تتطلب مرونة في الهيكل [3].

### 1.2.2. تصميم مخططات قواعد البيانات (Database Schemas) ومبادئ النمذجة

يجب أن يتم تصميم مخططات قواعد البيانات بعناية لضمان كفاءة تخزين البيانات واسترجاعها. تشمل المبادئ الأساسية:

*   **التطبيع (Normalization):** تقليل تكرار البيانات وتحسين تكاملها من خلال تقسيم الجداول إلى جداول أصغر وربطها بعلاقات. يساعد في تقليل حجم قاعدة البيانات وتحسين أداء الاستعلامات [3].
*   **الفهرسة (Indexing):** إنشاء فهارس على الأعمدة المستخدمة بشكل متكرر في الاستعلامات لتحسين سرعة البحث واسترجاع البيانات [3].
*   **العلاقات (Relationships):** تحديد العلاقات بين الجداول (واحد لواحد، واحد لمتعدد، متعدد لمتعدد) لضمان تكامل البيانات وتسهيل الاستعلامات المعقدة [3].

### 1.2.3. تخزين البيانات (Data Warehousing) وتحليلها

لتحليل البيانات التاريخية واستخراج رؤى قيمة، يمكن استخدام مستودعات البيانات (Data Warehouses). تُعد مستودعات البيانات قواعد بيانات مُحسّنة للاستعلامات التحليلية، وتخزن البيانات من مصادر متعددة في شكل مُجمّع. يمكن استخدام أدوات ذكاء الأعمال (Business Intelligence Tools) لتحليل هذه البيانات وإنشاء تقارير ولوحات معلومات [6].

## 1.3. تصميم واجهات برمجة التطبيقات (APIs) والتكامل

تُعد واجهات برمجة التطبيقات (APIs) هي البوابة التي تسمح للموديولات المختلفة داخل نظام ERP بالتفاعل مع بعضها البعض، ومع الأنظمة الخارجية. يجب أن تكون APIs مصممة بشكل جيد، موثقة، وآمنة لضمان التكامل السلس [7] [8].

### 1.3.1. مبادئ تصميم RESTful APIs

تُعد RESTful APIs هي المعيار الصناعي لتصميم واجهات برمجة التطبيقات على الويب. تعتمد على مبادئ REST (Representational State Transfer)، وتستخدم بروتوكول HTTP لإجراء العمليات (GET, POST, PUT, DELETE) على الموارد (Resources). تتميز بالبساطة، قابلية التوسع، والمرونة [7] [8].

### 1.3.2. استخدام GraphQL للتكامل المرن

GraphQL هي لغة استعلام للـ APIs وبيئة تشغيل لتنفيذ الاستعلامات باستخدام البيانات الموجودة لديك. تتيح للعملاء طلب البيانات التي يحتاجونها بالضبط، مما يقلل من حجم البيانات المنقولة ويحسن الأداء. يمكن استخدامها في السيناريوهات التي تتطلب مرونة عالية في استرجاع البيانات [7].

### 1.3.3. استراتيجيات التكامل مع الأنظمة الخارجية (Third-party Integrations)

*   **الربط المباشر (Direct Integration):** ربط نظام ERP مباشرة بالأنظمة الخارجية باستخدام APIs. مناسب للأنظمة التي تتطلب تكاملاً وثيقاً وتبادل بيانات في الوقت الفعلي [8].
*   **منصات التكامل (Integration Platforms):** استخدام منصات التكامل السحابية (iPaaS) لربط نظام ERP بالعديد من الأنظمة الخارجية. توفر هذه المنصات أدوات لتبسيط عملية التكامل وإدارة تدفقات البيانات [8].
*   **الرسائل وقوائم الانتظار (Messaging and Queues):** استخدام أنظمة الرسائل (مثل Kafka, RabbitMQ) لتبادل البيانات بين الأنظمة بشكل غير متزامن. مناسب للسيناريوهات التي تتطلب معالجة كميات كبيرة من البيانات أو التعامل مع الأنظمة التي قد تكون غير متوفرة بشكل مؤقت [8].

## 1.4. اعتبارات الأمان (Security Considerations)

يُعد أمان نظام ERP أمراً بالغ الأهمية لحماية البيانات الحساسة للشركة. يجب أن يتم تضمين اعتبارات الأمان في كل مرحلة من مراحل تصميم وتطوير النظام [15].

### 1.4.1. المصادقة (Authentication) والترخيص (Authorization)

*   **المصادقة:** التحقق من هوية المستخدم (مثل اسم المستخدم وكلمة المرور، المصادقة متعددة العوامل). يجب استخدام آليات مصادقة قوية لمنع الوصول غير المصرح به [15].
*   **الترخيص:** تحديد الصلاحيات التي يمتلكها المستخدم المصادق عليه (مثل الوصول إلى موديولات معينة، إجراء عمليات محددة). يجب تطبيق مبدأ الحد الأدنى من الامتيازات (Principle of Least Privilege) لضمان أن المستخدمين يمتلكون الصلاحيات اللازمة لأداء مهامهم فقط [15].

### 1.4.2. تشفير البيانات (Data Encryption) وحماية المعلومات الحساسة

يجب تشفير البيانات الحساسة (مثل البيانات المالية، بيانات العملاء) سواء كانت مخزنة في قاعدة البيانات (Encryption at Rest) أو أثناء نقلها عبر الشبكة (Encryption in Transit). يساعد ذلك في حماية البيانات من الوصول غير المصرح به حتى في حالة اختراق النظام [15].

### 1.4.3. إدارة الثغرات الأمنية (Vulnerability Management)

يجب إجراء اختبارات أمان منتظمة (مثل اختبار الاختراق، فحص الثغرات الأمنية) لتحديد ومعالجة أي نقاط ضعف في النظام. يجب أيضاً تحديث المكونات البرمجية بانتظام لضمان الحماية من أحدث التهديدات الأمنية [15].

## 1.5. قابلية التوسع والأداء (Scalability and Performance)

يجب أن يكون نظام ERP قادراً على التعامل مع زيادة حجم البيانات وعدد المستخدمين دون التأثير على الأداء. تُعد قابلية التوسع والأداء من العوامل الحاسمة لنجاح أي نظام ERP [1] [4].

### 1.5.1. تصميم الأنظمة القابلة للتوسع أفقياً وعمودياً

*   **التوسع الأفقي (Horizontal Scaling):** إضافة المزيد من الخوادم أو الموارد لزيادة قدرة النظام. يتم ذلك عادةً عن طريق توزيع الحمل على عدة خوادم (Load Balancing) أو استخدام قواعد بيانات موزعة (Distributed Databases) [4].
*   **التوسع العمودي (Vertical Scaling):** زيادة موارد الخادم الحالي (مثل إضافة المزيد من الذاكرة أو المعالجات). مناسب للأنظمة التي تتطلب أداءً عالياً ولكنها قد تصل إلى حدودها القصوى [4].

### 1.5.2. تحسين أداء قواعد البيانات والتطبيقات

*   **تحسين الاستعلامات (Query Optimization):** كتابة استعلامات فعالة لقواعد البيانات واستخدام الفهارس بشكل صحيح لتحسين سرعة استرجاع البيانات [4].
*   **التخزين المؤقت (Caching):** تخزين البيانات المستخدمة بشكل متكرر في الذاكرة المؤقتة لتقليل الحاجة إلى الوصول إلى قاعدة البيانات [4].
*   **تحسين الكود (Code Optimization):** كتابة كود فعال ومُحسّن لتقليل استهلاك الموارد وتحسين سرعة التنفيذ [4].

## 1.6. استراتيجيات النشر (Deployment Strategies)

تحدد استراتيجية النشر كيفية استضافة وتشغيل نظام ERP. يجب اختيار الاستراتيجية المناسبة بناءً على احتياجات الشركة، ميزانيتها، ومتطلبات الأمان [15].

### 1.6.1. النشر المحلي (On-premise)

يتم استضافة نظام ERP على خوادم الشركة الخاصة. يوفر هذا النموذج تحكماً كاملاً في البنية التحتية والبيانات، ولكنه يتطلب استثمارات كبيرة في الأجهزة، البرمجيات، وفريق الدعم [15].

### 1.6.2. النشر السحابي (Cloud Deployment)

يتم استضافة نظام ERP على خوادم مزود خدمة سحابية (مثل AWS, Azure, Google Cloud). يوفر هذا النموذج مرونة عالية، قابلية للتوسع، وتكاليف تشغيل أقل، ولكنه يتطلب الاعتماد على مزود الخدمة السحابية [15].

### 1.6.3. النشر الهجين (Hybrid Deployment)

يجمع هذا النموذج بين النشر المحلي والنشر السحابي. يمكن استضافة بعض الموديولات الحساسة محلياً، بينما يتم استضافة الموديولات الأخرى في السحابة. يوفر هذا النموذج مرونة في اختيار أفضل بيئة لكل مكون من مكونات النظام [15].

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftra.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftra.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الثاني: موديول إدارة المالية (Financial Management Module)

## 2.1. نظرة عامة على الموديول

![مخطط موديول إدارة المالية](Chapter_02_Financial_Management_Module.png)

يُعد موديول إدارة المالية (Financial Management Module) العمود الفقري لأي نظام ERP، حيث يتولى مسؤولية تسجيل، معالجة، وتحليل جميع المعاملات المالية للشركة. يهدف هذا الموديول إلى توفير رؤية شاملة ودقيقة للوضع المالي، مما يدعم اتخاذ القرارات الاستراتيجية ويضمن الامتثال للمعايير المحاسبية. تشمل الوظائف الرئيسية لهذا الموديول دفتر الأستاذ العام (General Ledger)، إدارة الذمم الدائنة (Accounts Payable)، إدارة الذمم المدينة (Accounts Receivable)، إدارة النقدية والبنوك (Cash and Bank Management)، وإدارة الأصول الثابتة (Fixed Assets Management) [13].

## 2.2. تصميم قاعدة البيانات

يعتمد تصميم قاعدة البيانات لموديول المالية على مبادئ المحاسبة، مع التركيز على المرونة والدقة لتمثيل الهيكل المالي للشركة. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 2.2.1. دليل الحسابات (Chart of Accounts)

يُعد دليل الحسابات هو الهيكل التنظيمي لجميع الحسابات المالية للشركة. يتم تمثيله عادةً في قاعدة البيانات كجدول هرمي يسمح بتصنيف الحسابات إلى مجموعات رئيسية وفرعية. يجب أن يكون مرناً بما يكفي لاستيعاب التغييرات المستقبلية في الهيكل المالي للشركة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `account_id`  | `INT (PK)`               | معرف الحساب الفريد |
| `account_code`| `VARCHAR(50)`            | كود الحساب (مثال: 1000-01-001) |
| `account_name`| `VARCHAR(255)`           | اسم الحساب (مثال: نقدية بالصندوق) |
| `account_type`| `ENUM`                   | نوع الحساب (أصول، خصوم، حقوق ملكية، إيرادات، مصروفات) |
| `parent_id`   | `INT (FK)`               | معرف الحساب الأم في الهيكل الهرمي |
| `is_active`   | `BOOLEAN`                | حالة الحساب (نشط/غير نشط) |

### 2.2.2. القيود اليومية (Journal Entries)

تُسجل جميع المعاملات المالية في شكل قيود يومية، والتي تعكس مبدأ القيد المزدوج (Double-Entry Bookkeeping). يتكون القيد اليومي من رأس (Header) يحتوي على معلومات عامة، وبنود (Lines) تفصيلية توضح الحسابات المدينة والدائنة.

**جدول `Journals` (رأس القيد اليومي):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `journal_id`  | `INT (PK)`               | معرف القيد اليومي الفريد |
| `journal_number`| `VARCHAR(50)`            | رقم القيد اليومي (تسلسلي) |
| `date`        | `DATE`                   | تاريخ القيد |
| `description` | `TEXT`                   | وصف عام للقيد |
| `total_debit` | `DECIMAL(18,2)`          | إجمالي الجانب المدين |
| `total_credit`| `DECIMAL(18,2)`          | إجمالي الجانب الدائن |
| `currency_code`| `VARCHAR(3)`             | رمز العملة (مثال: USD) |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي أنشأ القيد |
| `entity_type` | `ENUM`                   | نوع الكيان المرتبط (فاتورة، مصروف، إلخ) [10] |
| `entity_id`   | `INT`                    | معرف الكيان المرتبط [10] |

**جدول `JournalTransactions` (بنود القيد اليومي):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `transaction_id`| `INT (PK)`               | معرف حركة القيد الفريدة |
| `journal_id`  | `INT (FK)`               | معرف القيد اليومي المرتبط |
| `account_id`  | `INT (FK)`               | معرف الحساب المتأثر |
| `debit`       | `DECIMAL(18,2)`          | المبلغ المدين |
| `credit`      | `DECIMAL(18,2)`          | المبلغ الدائن |
| `description` | `TEXT`                   | وصف خاص بالحركة |
| `subkey`      | `ENUM`                   | مفتاح فرعي للكيان (عميل، مورد، إلخ) [10] |

### 2.2.3. المعاملات المالية الأخرى

بالإضافة إلى القيود اليومية، قد تتضمن قاعدة البيانات جداول لأنواع محددة من المعاملات مثل المصروفات (Expenses)، الإيرادات (Incomes)، والمدفوعات (Payments)، والتي يتم ربطها لاحقاً بالقيود اليومية أو تؤثر عليها بشكل مباشر.

**جدول `Expenses`:**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `expense_id`  | `INT (PK)`               | معرف المصروف الفريد |
| `date`        | `DATE`                   | تاريخ المصروف |
| `amount`      | `DECIMAL(18,2)`          | مبلغ المصروف |
| `description` | `TEXT`                   | وصف المصروف |
| `category_id` | `INT (FK)`               | معرف فئة المصروف |
| `vendor_id`   | `INT (FK)`               | معرف المورد (إن وجد) |

## 2.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المالية مجموعة من العمليات المعقدة التي تضمن دقة وسلامة البيانات المالية:

### 2.3.1. معالجة المعاملات (Transaction Processing)

عند إنشاء فاتورة مبيعات، أو تسجيل مصروف، أو استلام دفعة، يقوم النظام تلقائياً بإنشاء القيود المحاسبية اللازمة. يجب أن تضمن هذه العملية مبدأ القيد المزدوج، حيث يكون إجمالي الجانب المدين مساوياً لإجمالي الجانب الدائن لكل قيد [13].

### 2.3.2. ترحيل القيود إلى دفتر الأستاذ العام (GL Postings)

بعد إنشاء القيود اليومية، يتم ترحيلها إلى دفتر الأستاذ العام (General Ledger)، وهو السجل الرئيسي لجميع الحسابات المالية. يتم تحديث أرصدة الحسابات بشكل مستمر لتعكس أحدث المعاملات. يمكن أن يتم الترحيل بشكل فوري (Real-time) أو على دفعات (Batch Processing) [13].

### 2.3.3. التسويات البنكية (Bank Reconciliation)

تُعد التسوية البنكية عملية مطابقة أرصدة الحسابات البنكية في النظام مع كشوف الحسابات البنكية الفعلية. يتضمن المنطق البرمجي آليات لمقارنة المعاملات وتحديد أي فروقات، مما يضمن دقة سجلات النقدية والبنوك [13].

## 2.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs ضرورية لتمكين التفاعل بين موديول المالية والموديولات الأخرى، وكذلك مع الأنظمة الخارجية. فيما يلي أمثلة على APIs الرئيسية لموديول المالية:

*   `POST /journals`: لإنشاء قيد يومي جديد. يتطلب هذا الـ API بيانات رأس القيد (مثل `journal_number`, `date`, `description`, `total_debit`, `total_credit`, `currency_code`) وبنود القيد (مثل `account_id`, `debit`, `credit`) [10].
*   `GET /journals`: لاستعراض القيود اليومية. يمكن أن يدعم فلاتر للبحث حسب التاريخ، رقم القيد، أو نوع الكيان المرتبط [10].
*   `GET /journal_accounts`: لاستعراض دليل الحسابات. يمكن أن يدعم فلاتر للبحث حسب نوع الحساب أو اسم الحساب [10].
*   `GET /expenses`: لاستعراض المصروفات المسجلة. يمكن أن يدعم فلاتر للبحث حسب التاريخ، الفئة، أو المورد [10].
*   `POST /expenses`: لإضافة مصروف جديد. يتطلب بيانات المصروف مثل `date`, `amount`, `description`, `category_id` [10].
*   `GET /incomes`: لاستعراض الإيرادات المسجلة. يمكن أن يدعم فلاتر للبحث حسب التاريخ، الفئة، أو العميل [10].
*   `POST /incomes`: لإضافة إيراد جديد. يتطلب بيانات الإيراد مثل `date`, `amount`, `description`, `category_id` [10].

## 2.5. التقارير المالية

يوفر موديول المالية مجموعة من التقارير الأساسية التي تعكس الأداء المالي للشركة:

*   **قائمة الدخل (Income Statement):** تُظهر الإيرادات والمصروفات وصافي الربح أو الخسارة خلال فترة زمنية محددة. يتم تجميع البيانات من حسابات الإيرادات والمصروفات في دفتر الأستاذ العام [13].
*   **الميزانية العمومية (Balance Sheet):** تُقدم لقطة للوضع المالي للشركة في نقطة زمنية محددة، وتعرض الأصول والخصوم وحقوق الملكية. يتم تجميع البيانات من حسابات الأصول والخصوم وحقوق الملكية في دفتر الأستاذ العام [13].
*   **قائمة التدفقات النقدية (Cash Flow Statement):** تُوضح حركة النقدية الداخلة والخارجة من الأنشطة التشغيلية، الاستثمارية، والتمويلية. يتم تجميع البيانات من سجلات النقدية والبنوك [13].
*   **ميزان المراجعة (Trial Balance):** يُعد قائمة بجميع أرصدة الحسابات في دفتر الأستاذ العام في تاريخ معين، ويستخدم للتأكد من أن إجمالي الأرصدة المدينة يساوي إجمالي الأرصدة الدائنة [13].

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الثالث: موديول المبيعات والفواتير (Sales and Invoicing Module)

## 3.1. نظرة عامة على الموديول

![مخطط موديول المبيعات والفواتير](Chapter_03_Sales_and_Invoicing_Module.png)

يُعد موديول المبيعات والفواتير (Sales and Invoicing Module) جزءاً حيوياً من أي نظام ERP، حيث يدير جميع العمليات المتعلقة ببيع المنتجات والخدمات للعملاء. يهدف هذا الموديول إلى تبسيط دورة المبيعات، بدءاً من إنشاء عروض الأسعار وأوامر المبيعات، مروراً بإصدار الفواتير، وحتى تتبع المدفوعات. يضمن هذا الموديول كفاءة عمليات البيع، دقة الفواتير، وتحسين تجربة العملاء [2].

## 3.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول المبيعات والفواتير على تتبع جميع جوانب عملية البيع، من معلومات العميل والمنتج إلى تفاصيل الفاتورة والمدفوعات. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 3.2.1. أوامر المبيعات (Sales Orders)

تُسجل أوامر المبيعات طلبات العملاء للمنتجات أو الخدمات قبل إصدار الفاتورة النهائية. يمكن أن تمر أوامر المبيعات بحالات مختلفة (معلق، معتمد، منفذ جزئياً، منفذ بالكامل).

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `order_id`    | `INT (PK)`               | معرف أمر المبيعات الفريد |
| `order_number`| `VARCHAR(50)`            | رقم أمر المبيعات (تسلسلي) |
| `client_id`   | `INT (FK)`               | معرف العميل المرتبط |
| `order_date`  | `DATE`                   | تاريخ الطلب |
| `status`      | `ENUM`                   | حالة الطلب (معلق، معتمد، منفذ) |
| `total_amount`| `DECIMAL(18,2)`          | إجمالي مبلغ الطلب |
| `currency_code`| `VARCHAR(3)`             | رمز العملة |

### 3.2.2. الفواتير (Invoices)

تُعد الفواتير المستندات الرسمية التي تُصدر للعملاء لطلب الدفع مقابل المنتجات أو الخدمات المقدمة. تتكون الفاتورة من رأس (Header) وبنود (Items) تفصيلية.

**جدول `Invoices` (رأس الفاتورة):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `invoice_id`  | `INT (PK)`               | معرف الفاتورة الفريد |
| `invoice_number`| `VARCHAR(50)`            | رقم الفاتورة (تسلسلي) [10] |
| `client_id`   | `INT (FK)`               | معرف العميل المرتبط [10] |
| `date`        | `DATE`                   | تاريخ الفاتورة [10] |
| `due_date`    | `DATE`                   | تاريخ الاستحقاق |
| `total_amount`| `DECIMAL(18,2)`          | إجمالي مبلغ الفاتورة |
| `tax_amount`  | `DECIMAL(18,2)`          | مبلغ الضريبة |
| `discount_amount`| `DECIMAL(18,2)`          | مبلغ الخصم [10] |
| `currency_code`| `VARCHAR(3)`             | رمز العملة [10] |
| `status`      | `ENUM`                   | حالة الفاتورة (مدفوعة، مستحقة، جزئية) |
| `notes`       | `TEXT`                   | ملاحظات الفاتورة [10] |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي أنشأ الفاتورة [10] |

**جدول `InvoiceItems` (بنود الفاتورة):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `item_id`     | `INT (PK)`               | معرف البند الفريد |
| `invoice_id`  | `INT (FK)`               | معرف الفاتورة المرتبطة |
| `product_id`  | `INT (FK)`               | معرف المنتج المرتبط [10] |
| `item_name`   | `VARCHAR(255)`           | اسم المنتج/الخدمة [10] |
| `description` | `TEXT`                   | وصف البند [10] |
| `quantity`    | `DECIMAL(18,2)`          | الكمية [10] |
| `unit_price`  | `DECIMAL(18,2)`          | سعر الوحدة [10] |
| `total_price` | `DECIMAL(18,2)`          | إجمالي سعر البند |
| `tax1`        | `DECIMAL(18,2)`          | الضريبة الأولى [10] |
| `tax2`        | `DECIMAL(18,2)`          | الضريبة الثانية [10] |
| `discount`    | `DECIMAL(18,2)`          | خصم على البند [10] |

### 3.2.3. العملاء (Clients)

يتم ربط الفواتير بملفات العملاء المخزنة في موديول العملاء والموردين. يجب أن يتضمن جدول العملاء معلومات أساسية مثل الاسم، العنوان، ومعلومات الاتصال.

### 3.2.4. المنتجات (Products)

يتم ربط بنود الفواتير بالمنتجات أو الخدمات المخزنة في موديول المنتجات والمخزون. يجب أن يتضمن جدول المنتجات معلومات مثل اسم المنتج، الوصف، وسعر البيع.

## 3.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المبيعات والفواتير مجموعة من العمليات التي تضمن سير دورة المبيعات بسلاسة ودقة:

### 3.3.1. إنشاء أوامر المبيعات والفواتير

عند إنشاء أمر مبيعات أو فاتورة، يقوم النظام بالتحقق من توفر المنتجات في المخزون، وتطبيق قواعد التسعير والخصومات، وحساب الضرائب. يتم إنشاء قيد محاسبي تلقائي في موديول المالية لتسجيل الإيرادات والذمم المدينة [10].

### 3.3.2. تطبيق قواعد التسعير والخصومات

يمكن للنظام تطبيق قواعد تسعير مختلفة بناءً على العميل، الكمية، أو نوع المنتج. كما يمكن تطبيق خصومات على مستوى البند أو على إجمالي الفاتورة. يجب أن يكون المنطق البرمجي مرناً بما يكفي للتعامل مع هذه القواعد المعقدة [10].

### 3.3.3. تحديث حالة الفواتير

يتم تحديث حالة الفاتورة تلقائياً بناءً على المدفوعات المستلمة. يمكن أن تكون الفاتورة 
مدفوعة بالكامل، مدفوعة جزئياً، أو مستحقة. يتم إرسال تنبيهات للعملاء عند اقتراب موعد الاستحقاق أو عند تأخر الدفع.

## 3.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول المبيعات والفواتير ضرورية لتمكين إنشاء، استعراض، وتعديل الفواتير وأوامر المبيعات، بالإضافة إلى التكامل مع أنظمة أخرى مثل بوابات الدفع والمتاجر الإلكترونية.

*   `POST /invoices`: لإنشاء فاتورة جديدة. يتطلب هذا الـ API بيانات رأس الفاتورة (مثل `client_id`, `date`, `due_date`, `currency_code`, `discount_amount`, `notes`) وبنود الفاتورة (مثل `product_id`, `item_name`, `quantity`, `unit_price`, `tax1`, `tax2`, `discount`) [10].
*   `GET /invoices`: لاستعراض جميع الفواتير. يمكن أن يدعم فلاتر للبحث حسب العميل، التاريخ، الحالة، أو رقم الفاتورة [10].
*   `GET /invoices/{id}`: لاستعراض تفاصيل فاتورة محددة باستخدام معرف الفاتورة (`invoice_id`) [10].
*   `PUT /invoices/{id}`: لتعديل فاتورة موجودة. يتطلب معرف الفاتورة (`invoice_id`) والبيانات المراد تحديثها [10].
*   `DELETE /invoices/{id}`: لحذف فاتورة. يتطلب معرف الفاتورة (`invoice_id`). يجب أن يتم التحقق من عدم وجود مدفوعات مرتبطة بالفاتورة قبل الحذف [10].
*   `POST /sales_orders`: لإنشاء أمر مبيعات جديد. يتطلب بيانات مشابهة لإنشاء الفاتورة ولكن بحالة أولية مختلفة.
*   `GET /sales_orders`: لاستعراض أوامر المبيعات.

## 3.5. التقارير

يوفر موديول المبيعات والفواتير مجموعة من التقارير التحليلية التي تساعد في تقييم أداء المبيعات وتتبع الذمم المدينة:

*   **مبيعات حسب العميل (Sales by Customer):** يُظهر إجمالي المبيعات لكل عميل خلال فترة محددة، مما يساعد في تحديد العملاء الأكثر قيمة [6].
*   **مبيعات حسب المنتج (Sales by Product):** يُظهر المنتجات الأكثر مبيعاً والأقل مبيعاً، مما يساعد في إدارة المخزون وتخطيط الإنتاج [6].
*   **تحليل أعمار الفواتير (Invoice Aging):** يُصنف الفواتير المستحقة بناءً على مدة تأخرها (مثال: 0-30 يوم، 31-60 يوم، 61-90 يوم، أكثر من 90 يوم)، مما يساعد في إدارة التحصيلات [6].
*   **تقرير الإيرادات (Revenue Report):** يُقدم ملخصاً للإيرادات المحققة خلال فترة زمنية محددة، مع تفصيل حسب نوع المنتج أو الخدمة.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftra.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الرابع: موديول إدارة العملاء والموردين (Customer and Supplier Management Module)

## 4.1. نظرة عامة على الموديول

![مخطط موديول إدارة العملاء والموردين](Chapter_04_Customer_and_Supplier_Management_Module.png)

يُعد موديول إدارة العملاء والموردين (Customer and Supplier Management Module) بمثابة مركز معلومات لجميع الأطراف الخارجية التي تتعامل معها المؤسسة. يهدف هذا الموديول إلى تنظيم وتخزين بيانات العملاء والموردين بشكل مركزي، مما يسهل عمليات التواصل، المبيعات، المشتريات، وإدارة العلاقات. يضمن هذا الموديول دقة البيانات وتوفرها لجميع الموديولات الأخرى التي تتطلب معلومات عن العملاء والموردين [2].

## 4.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لهذا الموديول على التقاط جميع المعلومات ذات الصلة بالعملاء والموردين، بما في ذلك تفاصيل الاتصال، العناوين، والإعدادات المالية. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 4.2.1. ملفات العملاء (Client Profiles)

يخزن هذا الجدول المعلومات الأساسية والتفصيلية لكل عميل، سواء كان فرداً أو شركة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `client_id`   | `INT (PK)`               | معرف العميل الفريد |
| `client_type` | `ENUM`                   | نوع العميل (فردي، تجاري) |
| `first_name`  | `VARCHAR(100)`           | الاسم الأول للعميل (للأفراد) [10] |
| `last_name`   | `VARCHAR(100)`           | الاسم الأخير للعميل (للأفراد) [10] |
| `business_name`| `VARCHAR(255)`           | الاسم التجاري للعميل (للشركات) [10] |
| `email`       | `VARCHAR(255)`           | البريد الإلكتروني الأساسي [10] |
| `phone_number`| `VARCHAR(50)`            | رقم الهاتف الأساسي |
| `tax_id`      | `VARCHAR(50)`            | الرقم الضريبي للعميل (إن وجد) [10] |
| `credit_limit`| `DECIMAL(18,2)`          | الحد الائتماني المسموح به [10] |
| `credit_days` | `INT`                    | عدد أيام الائتمان المسموح بها [10] |
| `currency_code`| `VARCHAR(3)`             | العملة الافتراضية للعميل [10] |
| `price_group_id`| `INT (FK)`               | معرف مجموعة الأسعار المخصصة للعميل [10] |
| `category_id` | `INT (FK)`               | معرف فئة العميل (لتصنيف العملاء) [10] |
| `notes`       | `TEXT`                   | ملاحظات إضافية عن العميل [10] |
| `is_active`   | `BOOLEAN`                | حالة العميل (نشط/غير نشط) |

### 4.2.2. ملفات الموردين (Supplier Profiles)

يخزن هذا الجدول المعلومات الأساسية والتفصيلية لكل مورد تتعامل معه المؤسسة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `supplier_id` | `INT (PK)`               | معرف المورد الفريد |
| `supplier_name`| `VARCHAR(255)`           | اسم المورد (شركة أو فرد) |
| `contact_person`| `VARCHAR(255)`           | اسم جهة الاتصال الرئيسية لدى المورد |
| `email`       | `VARCHAR(255)`           | البريد الإلكتروني الأساسي |
| `phone_number`| `VARCHAR(50)`            | رقم الهاتف الأساسي |
| `tax_id`      | `VARCHAR(50)`            | الرقم الضريبي للمورد (إن وجد) |
| `payment_terms`| `VARCHAR(100)`           | شروط الدفع المتفق عليها |
| `currency_code`| `VARCHAR(3)`             | العملة الافتراضية للمورد |
| `notes`       | `TEXT`                   | ملاحظات إضافية عن المورد |
| `is_active`   | `BOOLEAN`                | حالة المورد (نشط/غير نشط) |

### 4.2.3. معلومات الاتصال والعناوين (Contact Information and Addresses)

يمكن أن يكون للعميل أو المورد الواحد عدة عناوين أو جهات اتصال. لذلك، يتم استخدام جداول منفصلة لربط هذه المعلومات بالكيان الرئيسي.

**جدول `Addresses`:**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `address_id`  | `INT (PK)`               | معرف العنوان الفريد |
| `entity_type` | `ENUM`                   | نوع الكيان (عميل، مورد) |
| `entity_id`   | `INT (FK)`               | معرف الكيان المرتبط |
| `address_line1`| `VARCHAR(255)`           | السطر الأول من العنوان [10] |
| `address_line2`| `VARCHAR(255)`           | السطر الثاني من العنوان (اختياري) [10] |
| `city`        | `VARCHAR(100)`           | المدينة [10] |
| `state`       | `VARCHAR(100)`           | الولاية/المقاطعة [10] |
| `postal_code` | `VARCHAR(20)`            | الرمز البريدي [10] |
| `country_code`| `VARCHAR(3)`             | رمز الدولة [10] |
| `is_shipping` | `BOOLEAN`                | هل هو عنوان شحن افتراضي؟ [10] |
| `is_billing`  | `BOOLEAN`                | هل هو عنوان فواتير افتراضي؟ |

**جدول `Contacts`:**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `contact_id`  | `INT (PK)`               | معرف جهة الاتصال الفريد |
| `entity_type` | `ENUM`                   | نوع الكيان (عميل، مورد) |
| `entity_id`   | `INT (FK)`               | معرف الكيان المرتبط |
| `name`        | `VARCHAR(255)`           | اسم جهة الاتصال |
| `email`       | `VARCHAR(255)`           | البريد الإلكتروني لجهة الاتصال |
| `phone_number`| `VARCHAR(50)`            | رقم الهاتف لجهة الاتصال |
| `role`        | `VARCHAR(100)`           | دور جهة الاتصال (مثال: مدير مبيعات) |

## 4.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول إدارة العملاء والموردين مجموعة من العمليات التي تضمن إدارة فعالة لبيانات جهات الاتصال:

### 4.3.1. إنشاء وتحديث ملفات العملاء والموردين

يتيح النظام للمستخدمين إنشاء ملفات جديدة للعملاء والموردين، وتحديث المعلومات الموجودة. يجب أن يتضمن المنطق البرمجي آليات للتحقق من صحة البيانات (Data Validation) لضمان إدخال معلومات دقيقة وكاملة، مثل التحقق من تنسيق البريد الإلكتروني أو رقم الهاتف [10].

### 4.3.2. إدارة العلاقات (Relationship Management)

يمكن للنظام تتبع العلاقات بين العملاء والموردين، مثل تحديد العملاء الذين هم أيضاً موردون، أو ربط جهات اتصال متعددة بعميل واحد. يساعد هذا في بناء رؤية شاملة لجميع التفاعلات مع الأطراف الخارجية.

### 4.3.3. تصنيف العملاء والموردين

يمكن تصنيف العملاء والموردين بناءً على معايير مختلفة (مثل الفئة، المنطقة الجغرافية، حجم الأعمال). يسهل هذا التصنيف عمليات الفلترة والبحث في التقارير، ويساعد في تطبيق استراتيجيات تسويقية أو شرائية مستهدفة [10].

## 4.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول إدارة العملاء والموردين ضرورية لتمكين الموديولات الأخرى من الوصول إلى بيانات جهات الاتصال وتحديثها، بالإضافة إلى التكامل مع أنظمة CRM أو أنظمة إدارة علاقات الموردين (SRM).

*   `GET /clients`: لاستعراض جميع العملاء. يمكن أن يدعم فلاتر للبحث حسب الاسم، البريد الإلكتروني، الفئة، أو الحالة [10].
*   `GET /clients/{id}`: لاستعراض تفاصيل عميل محدد باستخدام معرف العميل (`client_id`) [10].
*   `POST /clients`: لإضافة عميل جديد. يتطلب هذا الـ API بيانات العميل الأساسية مثل `client_type`, `first_name` أو `business_name`, `email`, `phone_number`, `tax_id`, `credit_limit`, `currency_code` [10].
*   `PUT /clients/{id}`: لتعديل بيانات عميل موجود. يتطلب معرف العميل (`client_id`) والبيانات المراد تحديثها [10].
*   `DELETE /clients/{id}`: لحذف عميل. يتطلب معرف العميل (`client_id`). يجب أن يتم التحقق من عدم وجود معاملات مالية أو فواتير مرتبطة بالعميل قبل الحذف [10].
*   `GET /suppliers`: لاستعراض جميع الموردين. يمكن أن يدعم فلاتر للبحث حسب الاسم، البريد الإلكتروني، أو الحالة [10].
*   `GET /suppliers/{id}`: لاستعراض تفاصيل مورد محدد باستخدام معرف المورد (`supplier_id`) [10].
*   `POST /suppliers`: لإضافة مورد جديد. يتطلب هذا الـ API بيانات المورد الأساسية مثل `supplier_name`, `contact_person`, `email`, `phone_number`, `tax_id`, `payment_terms`, `currency_code` [10].
*   `PUT /suppliers/{id}`: لتعديل بيانات مورد موجود. يتطلب معرف المورد (`supplier_id`) والبيانات المراد تحديثها [10].
*   `DELETE /suppliers/{id}`: لحذف مورد. يتطلب معرف المورد (`supplier_id`). يجب أن يتم التحقق من عدم وجود أوامر شراء أو فواتير مشتريات مرتبطة بالمورد قبل الحذف [10].

## 4.5. التقارير

يوفر موديول إدارة العملاء والموردين مجموعة من التقارير التي تساعد في تحليل العلاقات التجارية وتقييم الأداء:

*   **قائمة العملاء/الموردين (Client/Supplier List):** تقرير يعرض جميع العملاء أو الموردين مع معلوماتهم الأساسية [6].
*   **تقسيم العملاء (Customer Segmentation):** تقرير يقسم العملاء إلى مجموعات بناءً على معايير محددة (مثل حجم المبيعات، المنطقة الجغرافية) [6].
*   **تقييم أداء الموردين (Supplier Performance Evaluation):** تقرير يقيم أداء الموردين بناءً على معايير مثل جودة المنتجات، الالتزام بمواعيد التسليم، والأسعار [6].
*   **أعمار الذمم المدينة/الدائنة (Accounts Receivable/Payable Aging):** تقارير تفصيلية عن المبالغ المستحقة من العملاء أو للموردين، مصنفة حسب مدة الاستحقاق.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الخامس: موديول إدارة المنتجات والمخزون (Product and Inventory Management Module)

## 5.1. نظرة عامة على الموديول

![مخطط موديول إدارة المنتجات والمخزون](Chapter_05_Product_and_Inventory_Management_Module.png)

يُعد موديول إدارة المنتجات والمخزون (Product and Inventory Management Module) عنصراً حاسماً في أي نظام ERP، حيث يتولى مسؤولية تتبع وإدارة جميع المنتجات والسلع التي تتعامل بها المؤسسة. يهدف هذا الموديول إلى ضمان توفر المنتجات في الوقت المناسب، تحسين مستويات المخزون، وتقليل التكاليف المرتبطة بالتخزين. تشمل الوظائف الرئيسية لهذا الموديول كتالوج المنتجات، التحكم في المخزون، إدارة المستودعات، وتتبع حركات المخزون [2].

## 5.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول المنتجات والمخزون على التقاط جميع المعلومات المتعلقة بالمنتجات، مستويات المخزون، والمستودعات. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 5.2.1. المنتجات (Products)

يخزن هذا الجدول المعلومات الأساسية والتفصيلية لكل منتج أو خدمة تقدمها المؤسسة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `product_id`  | `INT (PK)`               | معرف المنتج الفريد |
| `product_name`| `VARCHAR(255)`           | اسم المنتج [10] |
| `sku`         | `VARCHAR(50)`            | رمز تعريف المنتج (Stock Keeping Unit) [10] |
| `description` | `TEXT`                   | وصف المنتج [10] |
| `category_id` | `INT (FK)`               | معرف فئة المنتج [10] |
| `unit_of_measure`| `VARCHAR(50)`            | وحدة القياس (مثال: قطعة، كجم) |
| `cost_price`  | `DECIMAL(18,2)`          | سعر التكلفة [10] |
| `sale_price`  | `DECIMAL(18,2)`          | سعر البيع [10] |
| `reorder_level`| `INT`                    | مستوى إعادة الطلب (عند الوصول إليه يتم طلب كمية جديدة) |
| `is_active`   | `BOOLEAN`                | حالة المنتج (نشط/غير نشط) |

**جدول `ProductCategories`:**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `category_id` | `INT (PK)`               | معرف الفئة الفريد |
| `category_name`| `VARCHAR(255)`           | اسم الفئة [10] |
| `parent_id`   | `INT (FK)`               | معرف الفئة الأم (للتصنيف الهرمي) |

### 5.2.2. مستويات المخزون (Inventory Levels)

يتتبع هذا الجدول الكمية المتوفرة من كل منتج في كل مستودع.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `inventory_id`| `INT (PK)`               | معرف المخزون الفريد |
| `product_id`  | `INT (FK)`               | معرف المنتج المرتبط |
| `store_id`    | `INT (FK)`               | معرف المستودع المرتبط [10] |
| `quantity_on_hand`| `DECIMAL(18,2)`          | الكمية المتوفرة حالياً |
| `reserved_quantity`| `DECIMAL(18,2)`          | الكمية المحجوزة (لأوامر المبيعات) |
| `available_quantity`| `DECIMAL(18,2)`          | الكمية المتاحة للبيع |

### 5.2.3. المستودعات (Warehouses)

يخزن هذا الجدول معلومات عن المستودعات المختلفة التي تمتلكها المؤسسة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `store_id`    | `INT (PK)`               | معرف المستودع الفريد [10] |
| `store_name`  | `VARCHAR(255)`           | اسم المستودع [10] |
| `location`    | `TEXT`                   | موقع المستودع |
| `is_active`   | `BOOLEAN`                | حالة المستودع (نشط/غير نشط) |

### 5.2.4. حركات المخزون (Stock Transactions)

يسجل هذا الجدول جميع الحركات التي تؤثر على مستويات المخزون، مثل الاستلام، الصرف، التحويل، والتسوية.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `transaction_id`| `INT (PK)`               | معرف الحركة الفريد |
| `product_id`  | `INT (FK)`               | معرف المنتج المتأثر |
| `store_id`    | `INT (FK)`               | معرف المستودع المتأثر |
| `transaction_type`| `ENUM`                   | نوع الحركة (استلام، صرف، تحويل، تسوية) |
| `quantity`    | `DECIMAL(18,2)`          | الكمية المتأثرة |
| `transaction_date`| `DATETIME`               | تاريخ ووقت الحركة |
| `reference_id`| `INT`                    | معرف المستند المرجعي (مثال: أمر شراء، فاتورة مبيعات) |
| `description` | `TEXT`                   | وصف الحركة |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي أجرى الحركة |

## 5.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المنتجات والمخزون مجموعة من العمليات التي تضمن إدارة فعالة ودقيقة للمخزون:

### 5.3.1. تعريف المنتجات وتصنيفها

يتيح النظام للمستخدمين إضافة منتجات جديدة، تحديد خصائصها (مثل SKU، سعر التكلفة، سعر البيع)، وتصنيفها ضمن فئات. يجب أن يدعم النظام أيضاً إدارة المتغيرات للمنتجات (مثل الألوان، الأحجام) [10].

### 5.3.2. تحديث أرصدة المخزون (Stock Updates)

يتم تحديث أرصدة المخزون تلقائياً عند حدوث أي حركة مخزنية. على سبيل المثال، عند استلام بضاعة من مورد، تزداد الكمية المتوفرة. وعند بيع منتج، تنقص الكمية المتوفرة. يجب أن تكون هذه العملية متزامنة ودقيقة لتجنب الأخطاء [10].

### 5.3.3. نقل المخزون بين المستودعات (Inter-warehouse Transfers)

يتيح النظام للمستخدمين نقل المنتجات بين المستودعات المختلفة. يجب أن يتم تسجيل هذه الحركات بدقة لضمان تتبع صحيح لموقع المنتجات [10].

### 5.3.4. تنبيهات انخفاض المخزون (Low Stock Alerts)

يقوم النظام بتوليد تنبيهات تلقائية عندما تصل كمية منتج معين في مستودع إلى مستوى إعادة الطلب المحدد. يساعد هذا في تجنب نقص المخزون وضمان توفر المنتجات بشكل مستمر [10].

### 5.3.5. جرد المخزون (Inventory Audit)

يجب أن يدعم النظام عمليات جرد المخزون الدورية (مثل الجرد الفعلي أو الجرد المستمر) لمطابقة الأرصدة الفعلية مع الأرصدة المسجلة في النظام. يتم تسجيل أي فروقات كتسويات مخزنية [12] [14].

## 5.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول المنتجات والمخزون ضرورية لتمكين الموديولات الأخرى (مثل المبيعات، المشتريات، نقطة البيع) من الوصول إلى معلومات المنتجات والمخزون وتحديثها.

*   `GET /products`: لاستعراض جميع المنتجات. يمكن أن يدعم فلاتر للبحث حسب الاسم، SKU، الفئة، أو الحالة [10].
*   `GET /products/{id}`: لاستعراض تفاصيل منتج محدد باستخدام معرف المنتج (`product_id`) [10].
*   `POST /products`: لإضافة منتج جديد. يتطلب هذا الـ API بيانات المنتج الأساسية مثل `product_name`, `sku`, `description`, `category_id`, `unit_of_measure`, `cost_price`, `sale_price` [10].
*   `PUT /products/{id}`: لتعديل بيانات منتج موجود. يتطلب معرف المنتج (`product_id`) والبيانات المراد تحديثها [10].
*   `DELETE /products/{id}`: لحذف منتج. يتطلب معرف المنتج (`product_id`). يجب أن يتم التحقق من عدم وجود حركات مخزنية أو فواتير مرتبطة بالمنتج قبل الحذف [10].
*   `GET /stores`: لاستعراض جميع المستودعات [10].
*   `GET /stores/{id}`: لاستعراض تفاصيل مستودع محدد [10].
*   `POST /stock_transactions`: لتسجيل حركة مخزنية جديدة. يتطلب هذا الـ API بيانات الحركة مثل `product_id`, `store_id`, `transaction_type`, `quantity`, `reference_id`, `description`, `staff_id` [10].
*   `GET /stock_transactions`: لاستعراض جميع حركات المخزون [10].

## 5.5. التقارير

يوفر موديول المنتجات والمخزون مجموعة من التقارير التي تساعد في إدارة المخزون وتحسين كفاءة العمليات:

*   **تقييم المخزون (Stock Valuation Report):** يُظهر القيمة الإجمالية للمخزون بناءً على سعر التكلفة أو سعر البيع [6].
*   **دوران المخزون (Inventory Turnover Report):** يُقيس مدى سرعة بيع المخزون واستبداله خلال فترة معينة [6].
*   **تحليل ABC للمخزون (ABC Analysis):** يُصنف المنتجات إلى فئات (A, B, C) بناءً على قيمتها وأهميتها، مما يساعد في تحديد أولويات الإدارة [6].
*   **تقرير حركة المخزون (Stock Movement Report):** يُظهر جميع الحركات التي تمت على منتج معين أو في مستودع معين خلال فترة محددة.
*   **تقرير المنتجات منخفضة المخزون (Low Stock Report):** يُدرج المنتجات التي وصلت كميتها إلى مستوى إعادة الطلب أو أقل.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب السادس: موديول إدارة المشتريات (Purchase Management Module)

## 6.1. نظرة عامة على الموديول

![مخطط موديول إدارة المشتريات](Chapter_06_Purchase_Management_Module.png)

يُعد موديول إدارة المشتريات (Purchase Management Module) جزءاً أساسياً من أي نظام ERP، حيث يتولى مسؤولية إدارة جميع العمليات المتعلقة بشراء السلع والخدمات من الموردين. يهدف هذا الموديول إلى تبسيط دورة الشراء، بدءاً من إنشاء طلبات الشراء، مروراً بإصدار أوامر الشراء، استلام البضائع، وحتى معالجة فواتير الموردين. يضمن هذا الموديول كفاءة عمليات الشراء، التحكم في التكاليف، وتحسين العلاقات مع الموردين [2].

## 6.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول المشتريات على تتبع جميع جوانب عملية الشراء، من معلومات المورد والمنتج إلى تفاصيل أمر الشراء وفاتورة المورد. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 6.2.1. أوامر الشراء (Purchase Orders)

تُسجل أوامر الشراء الطلبات الرسمية للمنتجات أو الخدمات من الموردين.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `po_id`       | `INT (PK)`               | معرف أمر الشراء الفريد |
| `po_number`   | `VARCHAR(50)`            | رقم أمر الشراء (تسلسلي) [10] |
| `supplier_id` | `INT (FK)`               | معرف المورد المرتبط [10] |
| `order_date`  | `DATE`                   | تاريخ الطلب [10] |
| `delivery_date`| `DATE`                   | تاريخ التسليم المتوقع [10] |
| `status`      | `ENUM`                   | حالة الطلب (معلق، معتمد، مستلم جزئياً، مستلم بالكامل) |
| `total_amount`| `DECIMAL(18,2)`          | إجمالي مبلغ الطلب [10] |
| `currency_code`| `VARCHAR(3)`             | رمز العملة [10] |
| `notes`       | `TEXT`                   | ملاحظات إضافية [10] |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي أنشأ أمر الشراء [10] |

**جدول `PurchaseOrderItems` (بنود أمر الشراء):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `item_id`     | `INT (PK)`               | معرف البند الفريد |
| `po_id`       | `INT (FK)`               | معرف أمر الشراء المرتبط |
| `product_id`  | `INT (FK)`               | معرف المنتج المرتبط [10] |
| `item_name`   | `VARCHAR(255)`           | اسم المنتج/الخدمة [10] |
| `description` | `TEXT`                   | وصف البند [10] |
| `quantity`    | `DECIMAL(18,2)`          | الكمية المطلوبة [10] |
| `unit_price`  | `DECIMAL(18,2)`          | سعر الوحدة المتفق عليه [10] |
| `total_price` | `DECIMAL(18,2)`          | إجمالي سعر البند [10] |
| `received_quantity`| `DECIMAL(18,2)`          | الكمية المستلمة حتى الآن |

### 6.2.2. فواتير المشتريات (Purchase Invoices)

تُسجل فواتير المشتريات الفواتير التي يتم استلامها من الموردين مقابل السلع أو الخدمات.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `purchase_invoice_id`| `INT (PK)`               | معرف فاتورة المشتريات الفريد |
| `invoice_number`| `VARCHAR(50)`            | رقم فاتورة المورد [10] |
| `supplier_id` | `INT (FK)`               | معرف المورد المرتبط [10] |
| `po_id`       | `INT (FK)`               | معرف أمر الشراء المرتبط (إن وجد) [10] |
| `date`        | `DATE`                   | تاريخ الفاتورة [10] |
| `due_date`    | `DATE`                   | تاريخ الاستحقاق [10] |
| `total_amount`| `DECIMAL(18,2)`          | إجمالي مبلغ الفاتورة [10] |
| `tax_amount`  | `DECIMAL(18,2)`          | مبلغ الضريبة [10] |
| `currency_code`| `VARCHAR(3)`             | رمز العملة [10] |
| `status`      | `ENUM`                   | حالة الفاتورة (مدفوعة، مستحقة، جزئية) |

### 6.2.3. استلام البضائع (Goods Receipt)

يتم تسجيل استلام البضائع كحركة مخزنية تؤثر على موديول المخزون، ولكن يمكن أن يكون هناك جدول منفصل لتتبع تفاصيل الاستلام.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `receipt_id`  | `INT (PK)`               | معرف الاستلام الفريد |
| `po_id`       | `INT (FK)`               | معرف أمر الشراء المرتبط |
| `product_id`  | `INT (FK)`               | معرف المنتج المستلم |
| `quantity`    | `DECIMAL(18,2)`          | الكمية المستلمة |
| `receipt_date`| `DATETIME`               | تاريخ ووقت الاستلام |
| `store_id`    | `INT (FK)`               | معرف المستودع الذي تم الاستلام فيه |

## 6.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المشتريات مجموعة من العمليات التي تضمن سير دورة الشراء بكفاءة ودقة:

### 6.3.1. إنشاء أوامر الشراء

عند إنشاء أمر شراء، يقوم النظام بالتحقق من معلومات المورد والمنتج، وتطبيق شروط الدفع المتفق عليها. يتم إنشاء قيد محاسبي تلقائي في موديول المالية لتسجيل الذمم الدائنة [10].

### 6.3.2. تسجيل استلام البضائع (Goods Receipt)

عند استلام البضائع من المورد، يتم تسجيل الكميات المستلمة ومطابقتها مع الكميات المطلوبة في أمر الشراء. يتم تحديث أرصدة المخزون في موديول المنتجات والمخزون تلقائياً [10].

### 6.3.3. مطابقة فواتير الموردين بأوامر الشراء (Three-Way Matching)

تُعد عملية المطابقة ثلاثية الأطراف (Three-Way Matching) ممارسة أساسية في إدارة المشتريات. تتضمن مطابقة فاتورة المورد مع أمر الشراء الأصلي وتقرير استلام البضائع. تضمن هذه العملية أن الشركة تدفع فقط مقابل السلع والخدمات التي تم طلبها واستلامها بالفعل [10].

## 6.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول المشتريات ضرورية لتمكين إنشاء، استعراض، وتعديل أوامر الشراء وفواتير الموردين، بالإضافة إلى التكامل مع أنظمة إدارة المخزون والمحاسبة.

*   `POST /purchase_invoices`: لإنشاء فاتورة مشتريات جديدة. يتطلب هذا الـ API بيانات رأس الفاتورة (مثل `supplier_id`, `invoice_number`, `date`, `due_date`, `total_amount`, `currency_code`) [10].
*   `GET /purchase_invoices`: لاستعراض جميع فواتير المشتريات. يمكن أن يدعم فلاتر للبحث حسب المورد، التاريخ، الحالة، أو رقم الفاتورة [10].
*   `GET /purchase_invoices/{id}`: لاستعراض تفاصيل فاتورة مشتريات محددة باستخدام معرف الفاتورة (`purchase_invoice_id`) [10].
*   `PUT /purchase_invoices/{id}`: لتعديل فاتورة مشتريات موجودة. يتطلب معرف الفاتورة (`purchase_invoice_id`) والبيانات المراد تحديثها [10].
*   `DELETE /purchase_invoices/{id}`: لحذف فاتورة مشتريات. يتطلب معرف الفاتورة (`purchase_invoice_id`). يجب أن يتم التحقق من عدم وجود مدفوعات مرتبطة بالفاتورة قبل الحذف [10].
*   `POST /purchase_orders`: لإنشاء أمر شراء جديد. يتطلب هذا الـ API بيانات رأس أمر الشراء (مثل `supplier_id`, `po_number`, `order_date`, `delivery_date`, `total_amount`, `currency_code`) وبنود أمر الشراء (مثل `product_id`, `quantity`, `unit_price`) [10].
*   `GET /purchase_orders`: لاستعراض جميع أوامر الشراء [10].

## 6.5. التقارير

يوفر موديول المشتريات مجموعة من التقارير التحليلية التي تساعد في تقييم أداء المشتريات وتتبع الذمم الدائنة:

*   **مشتريات حسب المورد (Purchases by Supplier):** يُظهر إجمالي المشتريات من كل مورد خلال فترة محددة [6].
*   **مشتريات حسب المنتج (Purchases by Product):** يُظهر المنتجات الأكثر شراءً والأقل شراءً، مما يساعد في إدارة المخزون والتفاوض مع الموردين [6].
*   **تحليل أعمار فواتير الموردين (Supplier Invoice Aging):** يُصنف فواتير الموردين المستحقة بناءً على مدة استحقاقها، مما يساعد في إدارة المدفوعات [6].
*   **تقرير أداء الموردين (Supplier Performance Report):** يُقيم أداء الموردين بناءً على معايير مثل جودة المنتجات، الالتزام بمواعيد التسليم، والأسعار.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب السابع: موديول نقطة البيع (Point of Sale - POS Module)

## 7.1. نظرة عامة على الموديول

![مخطط موديول نقطة البيع](Chapter_07_POS_Module.png)

يُعد موديول نقطة البيع (POS Module) واجهة أساسية للشركات التي تتعامل مع المبيعات المباشرة للعملاء، مثل متاجر التجزئة، المطاعم، والمقاهي. يهدف هذا الموديول إلى تبسيط عملية البيع بالتجزئة، من تسجيل المنتجات، معالجة المدفوعات، وحتى إصدار الإيصالات. يتكامل موديول POS بشكل وثيق مع موديولات المبيعات، المخزون، والمالية لضمان تحديث البيانات في الوقت الفعلي وتوفير رؤية شاملة لعمليات البيع [2].

## 7.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول نقطة البيع على تتبع معاملات البيع السريع، تفاصيل الإيصالات، وطرق الدفع. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 7.2.1. معاملات نقطة البيع (POS Transactions)

تُسجل هذه المعاملات كل عملية بيع تتم عبر نقطة البيع.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `pos_transaction_id`| `INT (PK)`               | معرف معاملة نقطة البيع الفريد |
| `transaction_date`| `DATETIME`               | تاريخ ووقت المعاملة |
| `store_id`    | `INT (FK)`               | معرف المتجر/المستودع الذي تمت فيه المعاملة |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي أجرى المعاملة |
| `client_id`   | `INT (FK)`               | معرف العميل (إن وجد) |
| `total_amount`| `DECIMAL(18,2)`          | إجمالي مبلغ المعاملة |
| `tax_amount`  | `DECIMAL(18,2)`          | مبلغ الضريبة |
| `discount_amount`| `DECIMAL(18,2)`          | مبلغ الخصم |
| `payment_method_id`| `INT (FK)`               | معرف طريقة الدفع المستخدمة |
| `status`      | `ENUM`                   | حالة المعاملة (مكتملة، معلقة، ملغاة) |

**جدول `POSTransactionItems` (بنود معاملة نقطة البيع):**

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `item_id`     | `INT (PK)`               | معرف البند الفريد |
| `pos_transaction_id`| `INT (FK)`               | معرف معاملة نقطة البيع المرتبطة |
| `product_id`  | `INT (FK)`               | معرف المنتج المرتبط |
| `item_name`   | `VARCHAR(255)`           | اسم المنتج/الخدمة |
| `quantity`    | `DECIMAL(18,2)`          | الكمية المباعة |
| `unit_price`  | `DECIMAL(18,2)`          | سعر الوحدة |
| `total_price` | `DECIMAL(18,2)`          | إجمالي سعر البند |

### 7.2.2. طرق الدفع (Payment Methods)

يخزن هذا الجدول طرق الدفع المختلفة التي يمكن استخدامها في نقطة البيع.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `payment_method_id`| `INT (PK)`               | معرف طريقة الدفع الفريد |
| `method_name` | `VARCHAR(100)`           | اسم طريقة الدفع (مثال: نقداً، بطاقة ائتمان، مدى) |
| `is_active`   | `BOOLEAN`                | حالة طريقة الدفع (نشط/غير نشط) |

## 7.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول نقطة البيع مجموعة من العمليات التي تضمن سير عملية البيع بسلاسة وسرعة:

### 7.3.1. معالجة المبيعات في الوقت الفعلي

عند إضافة منتج إلى سلة المشتريات، يقوم النظام بالتحقق من توفره في المخزون وتحديث الكميات المتاحة. عند إتمام عملية البيع، يتم خصم الكميات المباعة من المخزون وتحديث السجلات المالية في الوقت الفعلي [10].

### 7.3.2. تكامل مع أجهزة الدفع (Payment Gateway Integration)

يتكامل موديول POS مع بوابات الدفع الإلكترونية (مثل Stripe, PayPal) أو أجهزة نقاط البيع (POS Terminals) لمعالجة المدفوعات ببطاقات الائتمان أو الخصم. يجب أن يضمن هذا التكامل أمان المعاملات وسرعتها.

### 7.3.3. توليد الإيصالات (Receipt Generation)

بعد إتمام عملية البيع، يقوم النظام بتوليد إيصال (Receipt) للعميل، والذي يمكن طباعته أو إرساله عبر البريد الإلكتروني. يجب أن يتضمن الإيصال تفاصيل المعاملة، المنتجات المباعة، المبلغ الإجمالي، وطريقة الدفع.

### 7.3.4. إدارة المرتجعات (Returns Management)

يجب أن يدعم الموديول عملية إرجاع المنتجات، حيث يتم تحديث المخزون والسجلات المالية بشكل صحيح عند قبول المرتجعات.

## 7.4. واجهات برمجة التطبيقات (APIs)

يتكامل موديول POS بشكل أساسي مع APIs الموديولات الأخرى بدلاً من امتلاك APIs خاصة به لعمليات البيع الأساسية. ومع ذلك، قد تكون هناك APIs لإدارة إعدادات نقطة البيع أو استعراض ملخصات المبيعات.

*   **التكامل مع موديول المبيعات:** يستخدم APIs مثل `POST /invoices` لإنشاء فواتير مبيعات للمعاملات الكبيرة أو التي تتطلب تتبعاً مفصلاً [10].
*   **التكامل مع موديول المخزون:** يستخدم APIs مثل `POST /stock_transactions` لتحديث أرصدة المخزون عند البيع أو الإرجاع [10].
*   **التكامل مع موديول المالية:** يقوم بتوليد قيود يومية تلقائية لتسجيل الإيرادات والمدفوعات النقدية أو البنكية [10].

## 7.5. التقارير

يوفر موديول نقطة البيع مجموعة من التقارير التي تساعد في تحليل أداء المبيعات اليومي:

*   **ملخص المبيعات اليومية (Daily Sales Summary):** يُظهر إجمالي المبيعات، الضرائب، الخصومات، والمدفوعات لكل يوم عمل [6].
*   **مبيعات حسب طريقة الدفع (Sales by Payment Method):** يُوضح توزيع المبيعات على طرق الدفع المختلفة (نقداً، بطاقة، إلخ) [6].
*   **تقرير المنتجات المباعة (Products Sold Report):** يُدرج المنتجات الأكثر مبيعاً خلال فترة محددة.
*   **تقرير الموظفين (Staff Performance Report):** يُقيم أداء الموظفين في نقطة البيع بناءً على حجم المبيعات.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman's Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الثامن: موديول التقارير والتحليلات (Reports and Analytics Module)

## 8.1. نظرة عامة على الموديول

![مخطط موديول التقارير والتحليلات](Chapter_08_Reports_and_Analytics_Module.png)

يُعد موديول التقارير والتحليلات (Reports and Analytics Module) أداة حيوية في أي نظام ERP، حيث يوفر للمؤسسة القدرة على استخراج، تحليل، وعرض البيانات من جميع الموديولات الأخرى. يهدف هذا الموديول إلى تحويل البيانات الخام إلى معلومات قابلة للاستخدام، مما يدعم اتخاذ القرارات الاستراتيجية والتشغيلية. تشمل الوظائف الرئيسية لهذا الموديول توليد التقارير المالية، التشغيلية، المخزنية، بالإضافة إلى لوحات المعلومات التفاعلية (Dashboards) [6].

## 8.2. تصميم قاعدة البيانات

يعتمد تصميم قاعدة البيانات لموديول التقارير والتحليلات على تجميع البيانات من الموديولات الأخرى، وقد يتضمن جداول مخصصة لتخزين البيانات المجمعة أو تعريفات التقارير. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 8.2.1. بيانات التقارير المجمعة (Aggregated Report Data)

في بعض الحالات، خاصة للتقارير المعقدة أو التي تتطلب أداءً عالياً، قد يتم إنشاء جداول مخصصة لتخزين البيانات المجمعة أو المحسوبة مسبقاً. هذا يقلل من الحمل على قاعدة البيانات التشغيلية ويحسن سرعة توليد التقارير.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `report_data_id`| `INT (PK)`               | معرف البيانات المجمعة الفريد |
| `report_type` | `VARCHAR(100)`           | نوع التقرير (مثال: مبيعات شهرية) |
| `period_start_date`| `DATE`                   | تاريخ بداية الفترة |
| `period_end_date`| `DATE`                   | تاريخ نهاية الفترة |
| `total_sales` | `DECIMAL(18,2)`          | إجمالي المبيعات للفترة |
| `total_profit`| `DECIMAL(18,2)`          | إجمالي الأرباح للفترة |
| `product_id`  | `INT (FK)`               | معرف المنتج (إن كان التقرير خاصاً بمنتج) |

### 8.2.2. تعريفات التقارير (Report Definitions)

يسمح هذا الجدول بتخزين إعدادات التقارير المخصصة التي ينشئها المستخدمون، مما يتيح لهم حفظ قوالب التقارير وإعادة استخدامها.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `report_def_id`| `INT (PK)`               | معرف تعريف التقرير الفريد |
| `report_name` | `VARCHAR(255)`           | اسم التقرير |
| `report_description`| `TEXT`                   | وصف التقرير |
| `query_sql`   | `TEXT`                   | استعلام SQL المستخدم لتوليد التقرير |
| `parameters`  | `JSON`                   | معلمات التقرير (مثل نطاق التاريخ، الفلاتر) |
| `created_by`  | `INT (FK)`               | معرف المستخدم الذي أنشأ التقرير |
| `created_date`| `DATETIME`               | تاريخ إنشاء التقرير |

## 8.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول التقارير والتحليلات مجموعة من العمليات التي تضمن توليد تقارير دقيقة وذات مغزى:

### 8.3.1. محركات توليد التقارير (Report Generation Engines)

يجب أن يحتوي النظام على محركات قوية لتوليد التقارير، قادرة على استعلام قواعد البيانات، تجميع البيانات، وتطبيق الفلاتر والفرز. يمكن أن تكون هذه المحركات مبنية على SQL مباشرة أو تستخدم أدوات ETL (Extract, Transform, Load) لمعالجة البيانات قبل توليد التقرير [6].

### 8.3.2. تجميع البيانات وتحليلها (Data Aggregation and Analysis)

يقوم النظام بتجميع البيانات من موديولات مختلفة (مثل المالية، المبيعات، المخزون) وتحليلها لتقديم رؤى شاملة. يمكن أن يشمل ذلك حساب المجاميع، المتوسطات، النسب المئوية، والاتجاهات [6].

### 8.3.3. تخصيص التقارير (Custom Report Builder)

يجب أن يوفر الموديول واجهة للمستخدمين لإنشاء تقارير مخصصة بناءً على احتياجاتهم. يمكن أن يتضمن ذلك اختيار الحقول، تطبيق الفلاتر، تحديد نطاقات التاريخ، وتنسيق العرض [6].

## 8.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول التقارير والتحليلات ضرورية لتمكين الموديولات الأخرى من طلب التقارير، أو لتكامل النظام مع أدوات ذكاء الأعمال الخارجية.

*   `GET /reports/financial`: لاستعراض التقارير المالية (مثل قائمة الدخل، الميزانية العمومية). يمكن أن يدعم معلمات مثل `start_date`, `end_date` [10].
*   `GET /reports/sales`: لاستعراض تقارير المبيعات (مثل مبيعات حسب العميل، مبيعات حسب المنتج). يمكن أن يدعم معلمات مثل `client_id`, `product_id`, `start_date`, `end_date` [10].
*   `GET /reports/inventory`: لاستعراض تقارير المخزون (مثل تقييم المخزون، دوران المخزون). يمكن أن يدعم معلمات مثل `store_id`, `product_id` [10].
*   `POST /reports/custom`: لإنشاء تقرير مخصص بناءً على تعريف تقرير محدد أو معلمات مقدمة [10].

## 8.5. أنواع التقارير

يوفر موديول التقارير والتحليلات مجموعة واسعة من التقارير لتلبية احتياجات الأقسام المختلفة:

*   **التقارير المالية (Financial Reports):** تشمل قائمة الدخل، الميزانية العمومية، قائمة التدفقات النقدية، وميزان المراجعة [13].
*   **تقارير المبيعات والمشتريات (Sales and Purchase Reports):** تشمل مبيعات حسب العميل، مبيعات حسب المنتج، مشتريات حسب المورد، وتحليل أعمار الفواتير [6].
*   **تقارير المخزون (Inventory Reports):** تشمل تقييم المخزون، دوران المخزون، تحليل ABC، وتقرير حركة المخزون [6].
*   **لوحات المعلومات التفاعلية (Interactive Dashboards):** تُقدم نظرة عامة مرئية على مؤشرات الأداء الرئيسية (KPIs) للشركة، مع إمكانية التفاعل مع البيانات وتصفيتها [6].

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman\'s Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب التاسع: موديول التدقيق والامتثال (Audit and Compliance Module)

## 9.1. نظرة عامة على الموديول

![مخطط موديول التدقيق والامتثال](Chapter_09_Audit_and_Compliance_Module.png)

يُعد موديول التدقيق والامتثال (Audit and Compliance Module) ضرورياً لضمان الشفافية، المساءلة، والالتزام باللوائح الداخلية والخارجية داخل نظام ERP. يهدف هذا الموديول إلى تتبع جميع الأنشطة الهامة التي تتم داخل النظام، وتسجيلها في سجلات تدقيق مفصلة، ومراقبة الامتثال للسياسات والإجراءات. يساعد هذا الموديول المؤسسات على تحديد المخاطر، التحقيق في الحوادث، وتقديم الأدلة اللازمة لعمليات التدقيق الخارجية [12].

## 9.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول التدقيق والامتثال على تسجيل تفاصيل الأنشطة وسجلات التدقيق، بالإضافة إلى تتبع نتائج التدقيق. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 9.2.1. سجل الأنشطة (Activity Log)

يسجل هذا الجدول جميع الإجراءات الهامة التي تتم داخل النظام، مما يوفر مسار تدقيق كاملاً.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `log_id`      | `INT (PK)`               | معرف السجل الفريد |
| `timestamp`   | `DATETIME`               | تاريخ ووقت الإجراء |
| `staff_id`    | `INT (FK)`               | معرف الموظف الذي قام بالإجراء |
| `action_type` | `VARCHAR(100)`           | نوع الإجراء (مثال: إنشاء، تعديل، حذف، تسجيل دخول) |
| `module_name` | `VARCHAR(100)`           | الموديول الذي تم فيه الإجراء |
| `entity_type` | `VARCHAR(100)`           | نوع الكيان المتأثر (مثال: فاتورة، منتج، عميل) |
| `entity_id`   | `INT`                    | معرف الكيان المتأثر |
| `old_value`   | `JSON`                   | القيمة القديمة للبيانات (قبل التعديل) |
| `new_value`   | `JSON`                   | القيمة الجديدة للبيانات (بعد التعديل) |
| `ip_address`  | `VARCHAR(45)`            | عنوان IP للمستخدم |

### 9.2.2. نتائج التدقيق (Audit Findings)

يخزن هذا الجدول نتائج عمليات التدقيق، بما في ذلك أي ملاحظات، توصيات، أو انتهاكات تم اكتشافها.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `finding_id`  | `INT (PK)`               | معرف نتيجة التدقيق الفريد |
| `audit_date`  | `DATE`                   | تاريخ عملية التدقيق |
| `description` | `TEXT`                   | وصف تفصيلي لنتيجة التدقيق |
| `severity`    | `ENUM`                   | مستوى الخطورة (منخفض، متوسط، مرتفع) |
| `status`      | `ENUM`                   | حالة النتيجة (مفتوحة، قيد المعالجة، مغلقة) |
| `assigned_to` | `INT (FK)`               | معرف الموظف المسؤول عن معالجة النتيجة |
| `due_date`    | `DATE`                   | تاريخ الاستحقاق لمعالجة النتيجة |
| `resolution_details`| `TEXT`                   | تفاصيل الحل أو الإجراء التصحيحي |

## 9.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول التدقيق والامتثال مجموعة من العمليات التي تضمن تتبعاً دقيقاً للأنشطة ومراقبة فعالة للامتثال:

### 9.3.1. تسجيل جميع الإجراءات الهامة على النظام

يجب أن يقوم النظام بتسجيل جميع الإجراءات التي قد تكون ذات أهمية للتدقيق، مثل إنشاء، تعديل، أو حذف السجلات المالية، أو تغيير صلاحيات المستخدمين. يتم تسجيل هذه الإجراءات تلقائياً في جدول `AuditLogs` مع جميع التفاصيل ذات الصلة [12].

### 9.3.2. تحليل سجلات التدقيق لتحديد الأنماط المشبوهة

يمكن للموديول استخدام خوارزميات تحليل البيانات لتحديد الأنماط المشبوهة أو غير المعتادة في سجلات التدقيق، مثل محاولات تسجيل الدخول الفاشلة المتكررة، أو التعديلات على البيانات الحساسة من قبل مستخدمين غير مصرح لهم. يمكن أن يؤدي ذلك إلى توليد تنبيهات تلقائية للمسؤولين [12].

### 9.3.3. إدارة دورة حياة نتائج التدقيق (Finding Lifecycle Management)

يتيح الموديول للمستخدمين تسجيل نتائج التدقيق، وتعيينها للموظفين المسؤولين، وتتبع حالتها من الاكتشاف وحتى الحل. يجب أن يدعم النظام أيضاً إرفاق المستندات والأدلة المتعلقة بكل نتيجة تدقيق [12].

## 9.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول التدقيق والامتثال ضرورية لتمكين الموديولات الأخرى من تسجيل الأنشطة، وللسماح للمدققين بالوصول إلى سجلات التدقيق ونتائجه.

*   `POST /audit_logs`: لتسجيل نشاط جديد في سجل التدقيق. يتم استدعاء هذا الـ API تلقائياً من قبل الموديولات الأخرى عند حدوث إجراء هام [10].
*   `GET /audit_logs`: لاستعراض سجلات التدقيق. يمكن أن يدعم فلاتر للبحث حسب الموظف، نوع الإجراء، الموديول، أو نطاق التاريخ [10].
*   `POST /audit_findings`: لتسجيل نتيجة تدقيق جديدة. يتطلب هذا الـ API بيانات النتيجة مثل `audit_date`, `description`, `severity`, `status`, `assigned_to`, `due_date` [10].
*   `GET /audit_findings`: لاستعراض نتائج التدقيق. يمكن أن يدعم فلاتر للبحث حسب الحالة، مستوى الخطورة، أو الموظف المسؤول [10].
*   `PUT /audit_findings/{id}`: لتحديث حالة أو تفاصيل نتيجة تدقيق موجودة [10].

## 9.5. التقارير

يوفر موديول التدقيق والامتثال مجموعة من التقارير التي تساعد في مراقبة الامتثال وتقييم الأمان:

*   **تقرير سجل الأنشطة (Activity Log Report):** يُظهر جميع الأنشطة التي تمت في النظام خلال فترة محددة، مع تفاصيل عن المستخدم، الإجراء، والكيان المتأثر [6].
*   **تقرير حالة الامتثال (Compliance Status Report):** يُقدم نظرة عامة على مدى التزام الشركة بالسياسات والإجراءات، ويُظهر أي انتهاكات تم اكتشافها [6].
*   **تقرير نتائج التدقيق (Audit Findings Report):** يُدرج جميع نتائج التدقيق، حالتها، ومستوى خطورتها، مع تفاصيل عن الإجراءات التصحيحية المتخذة [6].
*   **تقرير المستخدمين النشطين (Active Users Report):** يُظهر قائمة بالمستخدمين الذين قاموا بتسجيل الدخول والأنشطة التي قاموا بها.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman\'s Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب العاشر: موديول المخاطر والتنبؤ (Risk and Forecasting Module)

## 10.1. نظرة عامة على الموديول

![مخطط موديول المخاطر والتنبؤ](Chapter_10_Risk_and_Forecasting_Module.png)

يُعد موديول المخاطر والتنبؤ (Risk and Forecasting Module) أداة استراتيجية في نظام ERP، حيث يوفر للمؤسسة القدرة على تحديد، تقييم، ومراقبة المخاطر المحتملة، بالإضافة إلى التنبؤ بالاتجاهات المستقبلية بناءً على البيانات التاريخية. يهدف هذا الموديول إلى دعم اتخاذ القرارات الاستباقية، تقليل عدم اليقين، وتحسين التخطيط للمستقبل. تشمل الوظائف الرئيسية لهذا الموديول تقييم المخاطر، التنبؤ بالاتجاهات، ومؤشرات المخاطر الرئيسية [6].

## 10.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول المخاطر والتنبؤ على تخزين معلومات المخاطر، والبيانات التاريخية المستخدمة في التنبؤات، ونتائج نماذج التنبؤ. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 10.2.1. سجل المخاطر (Risk Register)

يسجل هذا الجدول جميع المخاطر المحتملة التي قد تواجه المؤسسة، مع تفاصيل عن طبيعة المخاطرة، احتمالية حدوثها، وتأثيرها المحتمل.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `risk_id`     | `INT (PK)`               | معرف المخاطرة الفريد |
| `risk_name`   | `VARCHAR(255)`           | اسم المخاطرة |
| `description` | `TEXT`                   | وصف تفصيلي للمخاطرة |
| `category`    | `ENUM`                   | فئة المخاطرة (مثال: مالية، تشغيلية، استراتيجية) |
| `probability` | `DECIMAL(5,2)`           | احتمالية الحدوث (0-1) |
| `impact`      | `DECIMAL(5,2)`           | التأثير المحتمل (0-1) |
| `risk_score`  | `DECIMAL(5,2)`           | درجة المخاطرة (الاحتمالية * التأثير) |
| `mitigation_plan`| `TEXT`                   | خطة التخفيف من المخاطر |
| `status`      | `ENUM`                   | حالة المخاطرة (مفتوحة، قيد المعالجة، مغلقة) |
| `owner_staff_id`| `INT (FK)`               | معرف الموظف المسؤول عن المخاطرة |

### 10.2.2. بيانات التنبؤ (Forecasting Data)

يتم تخزين البيانات التاريخية من الموديولات الأخرى (مثل المبيعات، المشتريات، المخزون) في جداول مخصصة أو يتم الوصول إليها مباشرة من الجداول الأصلية. قد يتم أيضاً تخزين نتائج نماذج التنبؤ في جداول منفصلة.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `forecast_id` | `INT (PK)`               | معرف التنبؤ الفريد |
| `forecast_type`| `VARCHAR(100)`           | نوع التنبؤ (مثال: مبيعات، مخزون) |
| `period_start_date`| `DATE`                   | تاريخ بداية فترة التنبؤ |
| `period_end_date`| `DATE`                   | تاريخ نهاية فترة التنبؤ |
| `predicted_value`| `DECIMAL(18,2)`          | القيمة المتنبأ بها |
| `actual_value`| `DECIMAL(18,2)`          | القيمة الفعلية (بعد تحققها) |
| `model_used`  | `VARCHAR(255)`           | اسم نموذج التنبؤ المستخدم |
| `created_date`| `DATETIME`               | تاريخ إنشاء التنبؤ |

## 10.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المخاطر والتنبؤ مجموعة من العمليات التحليلية والإحصائية:

### 10.3.1. نماذج تقييم المخاطر (Risk Assessment Models)

يجب أن يوفر الموديول أدوات لتقييم المخاطر بناءً على معايير محددة (مثل الاحتمالية والتأثير). يمكن استخدام مصفوفات المخاطر (Risk Matrices) لتصنيف المخاطر وتحديد أولوياتها. يتم حساب درجة المخاطرة (Risk Score) تلقائياً بناءً على هذه المعايير [6].

### 10.3.2. خوارزميات التنبؤ (Forecasting Algorithms)

يجب أن يدعم الموديول مجموعة متنوعة من خوارزميات التنبؤ، مثل تحليل السلاسل الزمنية (Time Series Analysis) (مثل ARIMA, Exponential Smoothing)، الانحدار الخطي (Linear Regression)، أو نماذج التعلم الآلي (Machine Learning Models). يتم تطبيق هذه الخوارزميات على البيانات التاريخية للتنبؤ بالاتجاهات المستقبلية في المبيعات، الطلب، أو المخزون [6].

### 10.3.3. تحليل السيناريوهات (Scenario Analysis)

يتيح الموديول للمستخدمين إنشاء سيناريوهات مختلفة (مثل سيناريو أفضل حالة، أسوأ حالة، حالة واقعية) وتقييم تأثيرها المحتمل على الأعمال. يساعد هذا في التخطيط للطوارئ واتخاذ قرارات أكثر استنارة [6].

## 10.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول المخاطر والتنبؤ ضرورية لتمكين الموديولات الأخرى من الوصول إلى معلومات المخاطر والتنبؤات، أو لتكامل النظام مع أدوات تحليل البيانات الخارجية.

*   `GET /risks`: لاستعراض جميع المخاطر المسجلة. يمكن أن يدعم فلاتر للبحث حسب الفئة، الحالة، أو الموظف المسؤول [10].
*   `POST /risks`: لإضافة مخاطرة جديدة. يتطلب هذا الـ API بيانات المخاطرة مثل `risk_name`, `description`, `category`, `probability`, `impact`, `mitigation_plan`, `owner_staff_id` [10].
*   `PUT /risks/{id}`: لتعديل تفاصيل مخاطرة موجودة [10].
*   `GET /forecasts`: لاستعراض التنبؤات. يمكن أن يدعم فلاتر للبحث حسب نوع التنبؤ، فترة التنبؤ، أو النموذج المستخدم [10].
*   `POST /forecasts`: لإنشاء تنبؤ جديد بناءً على بيانات محددة ونموذج تنبؤ [10].

## 10.5. التقارير

يوفر موديول المخاطر والتنبؤ مجموعة من التقارير التي تساعد في إدارة المخاطر والتخطيط للمستقبل:

*   **لوحة معلومات المخاطر (Risk Dashboard):** تُقدم نظرة عامة مرئية على المخاطر الرئيسية التي تواجه المؤسسة، مع مؤشرات لدرجة المخاطرة وحالة خطط التخفيف [6].
*   **تقرير سجل المخاطر (Risk Register Report):** يُدرج جميع المخاطر المسجلة مع تفاصيلها الكاملة، بما في ذلك خطط التخفيف والمسؤولين [6].
*   **تقارير التنبؤ (Forecasting Reports):** تُعرض التنبؤات المستقبلية للمبيعات، الطلب، أو أي مؤشرات أخرى، مع مقارنة بالقيم الفعلية بعد تحققها [6].
*   **تحليل الحساسية (Sensitivity Analysis Report):** يُظهر كيف تتغير نتائج التنبؤات بناءً على التغيرات في المتغيرات الرئيسية.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman\"s Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الحادي عشر: موديول الإعدادات العامة (General Settings Module)

## 11.1. نظرة عامة على الموديول

![مخطط موديول الإعدادات العامة](Chapter_11_General_Settings_Module.png)

يُعد موديول الإعدادات العامة (General Settings Module) مركز التحكم المركزي لنظام ERP، حيث يتيح للمسؤولين تهيئة النظام ليناسب احتياجات المؤسسة المحددة. يهدف هذا الموديول إلى توفير المرونة في تخصيص سلوك النظام، من معلومات الشركة الأساسية إلى الإعدادات المالية، خيارات الأقلمة، والمظهر العام. كما يدير هذا الموديول إعدادات الربط البرمجي (API) لتمكين التكامل مع الأنظمة الخارجية [10].

## 11.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول الإعدادات العامة على تخزين جميع التكوينات والإعدادات التي تؤثر على سلوك النظام. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 11.2.1. إعدادات الشركة (Company Settings)

يخزن هذا الجدول المعلومات الأساسية عن الشركة التي تستخدم نظام ERP.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `company_id`  | `INT (PK)`               | معرف الشركة الفريد |
| `company_name`| `VARCHAR(255)`           | اسم الشركة |
| `address`     | `TEXT`                   | عنوان الشركة |
| `phone_number`| `VARCHAR(50)`            | رقم هاتف الشركة |
| `email`       | `VARCHAR(255)`           | البريد الإلكتروني للشركة |
| `tax_id`      | `VARCHAR(50)`            | الرقم الضريبي للشركة |
| `logo_url`    | `VARCHAR(255)`           | رابط شعار الشركة |

### 11.2.2. الإعدادات المالية (Financial Settings)

يخزن هذا الجدول الإعدادات المتعلقة بالجوانب المالية والمحاسبية للنظام.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `setting_id`  | `INT (PK)`               | معرف الإعداد الفريد |
| `company_id`  | `INT (FK)`               | معرف الشركة المرتبطة |
| `base_currency`| `VARCHAR(3)`             | العملة الأساسية للنظام |
| `default_tax_rate`| `DECIMAL(5,2)`           | نسبة الضريبة الافتراضية |
| `fiscal_year_start`| `DATE`                   | تاريخ بداية السنة المالية |
| `invoice_prefix`| `VARCHAR(10)`            | بادئة أرقام الفواتير |
| `journal_prefix`| `VARCHAR(10)`            | بادئة أرقام القيود اليومية |

### 11.2.3. إعدادات الأقلمة (Localization Settings)

يخزن هذا الجدول الإعدادات المتعلقة باللغة، المنطقة الزمنية، وتنسيقات التاريخ والوقت.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `setting_id`  | `INT (PK)`               | معرف الإعداد الفريد |
| `company_id`  | `INT (FK)`               | معرف الشركة المرتبطة |
| `language_code`| `VARCHAR(10)`            | رمز اللغة الافتراضية (مثال: ar, en) |
| `timezone`    | `VARCHAR(50)`            | المنطقة الزمنية الافتراضية |
| `date_format` | `VARCHAR(50)`            | تنسيق التاريخ الافتراضي |
| `time_format` | `VARCHAR(50)`            | تنسيق الوقت الافتراضي |

### 11.2.4. إعدادات API (API Settings)

يخزن هذا الجدول مفاتيح API المستخدمة للتكامل مع الأنظمة الخارجية، بالإضافة إلى إعدادات الأمان المتعلقة بها.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `api_key_id`  | `INT (PK)`               | معرف مفتاح API الفريد |
| `company_id`  | `INT (FK)`               | معرف الشركة المرتبطة |
| `api_key`     | `VARCHAR(255)`           | مفتاح API (مشفر) |
| `description` | `TEXT`                   | وصف لمفتاح API (الغرض منه) |
| `created_by`  | `INT (FK)`               | معرف المستخدم الذي أنشأ المفتاح |
| `created_date`| `DATETIME`               | تاريخ إنشاء المفتاح |
| `is_active`   | `BOOLEAN`                | حالة المفتاح (نشط/غير نشط) |

## 11.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول الإعدادات العامة مجموعة من العمليات التي تضمن تطبيق التكوينات بشكل صحيح على مستوى النظام:

### 11.3.1. إدارة بيانات الشركة

يتيح النظام للمسؤولين تحديث معلومات الشركة الأساسية، مثل الاسم، العنوان، ومعلومات الاتصال. يتم استخدام هذه المعلومات في جميع أنحاء النظام، مثل الفواتير والتقارير.

### 11.3.2. تطبيق الإعدادات على مستوى النظام

يتم تطبيق الإعدادات المخزنة في هذا الموديول على جميع الموديولات الأخرى. على سبيل المثال، يتم استخدام العملة الأساسية في جميع المعاملات المالية، ويتم استخدام تنسيق التاريخ الافتراضي في جميع العروض والتقارير.

### 11.3.3. توليد مفاتيح API وإدارتها

يتيح الموديول للمسؤولين توليد مفاتيح API جديدة، وتعيين صلاحيات محددة لكل مفتاح، وتتبع استخدامها. يجب أن يتم تخزين مفاتيح API بشكل آمن (مشفرة) وأن يتم توفير آليات لإلغاء تنشيطها عند الحاجة [10].

## 11.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول الإعدادات العامة ضرورية لتمكين الموديولات الأخرى من الوصول إلى الإعدادات، وللسماح للمسؤولين بتحديثها برمجياً.

*   `GET /settings`: لاستعراض جميع الإعدادات العامة للشركة. يمكن أن يدعم فلاتر للبحث حسب نوع الإعداد [10].
*   `PUT /settings`: لتحديث إعدادات عامة محددة. يتطلب هذا الـ API معرف الإعداد والبيانات المراد تحديثها [10].
*   `POST /api_keys`: لتوليد مفتاح API جديد. يتطلب هذا الـ API وصفاً للمفتاح والصلاحيات المراد منحها [10].
*   `GET /api_keys`: لاستعراض جميع مفاتيح API الموجودة [10].
*   `PUT /api_keys/{id}`: لتحديث حالة أو صلاحيات مفتاح API موجود [10].
*   `DELETE /api_keys/{id}`: لحذف مفتاح API [10].

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman\"s Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
# الباب الثاني عشر: موديول المستخدمين والصلاحيات (Users and Roles Module)

## 12.1. نظرة عامة على الموديول

![مخطط موديول المستخدمين والصلاحيات](Chapter_12_Users_and_Roles_Module.png)

يُعد موديول المستخدمين والصلاحيات (Users and Roles Module) عنصراً حيوياً في أي نظام ERP، حيث يتولى مسؤولية إدارة الوصول إلى النظام وموارده. يهدف هذا الموديول إلى ضمان أن المستخدمين المصرح لهم فقط هم من يمكنهم الوصول إلى البيانات والوظائف المناسبة، مما يحافظ على أمان النظام وسلامة البيانات. تشمل الوظائف الرئيسية لهذا الموديول إدارة حسابات المستخدمين، تعريف الأدوار، تخصيص الصلاحيات، وتتبع نشاط المستخدمين [15].

## 12.2. تصميم قاعدة البيانات

يركز تصميم قاعدة البيانات لموديول المستخدمين والصلاحيات على تخزين معلومات المستخدمين، الأدوار، والصلاحيات، بالإضافة إلى ربطها ببعضها البعض. فيما يلي المكونات الرئيسية لتصميم قاعدة البيانات:

### 12.2.1. المستخدمون (Users)

يخزن هذا الجدول المعلومات الأساسية لكل مستخدم يمكنه الوصول إلى نظام ERP.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `user_id`     | `INT (PK)`               | معرف المستخدم الفريد |
| `username`    | `VARCHAR(100)`           | اسم المستخدم (فريد) |
| `email`       | `VARCHAR(255)`           | البريد الإلكتروني للمستخدم (فريد) |
| `password_hash`| `VARCHAR(255)`           | كلمة المرور المشفرة |
| `first_name`  | `VARCHAR(100)`           | الاسم الأول للمستخدم |
| `last_name`   | `VARCHAR(100)`           | الاسم الأخير للمستخدم |
| `is_active`   | `BOOLEAN`                | حالة الحساب (نشط/غير نشط) |
| `created_date`| `DATETIME`               | تاريخ إنشاء الحساب |
| `last_login`  | `DATETIME`               | آخر تاريخ تسجيل دخول |

### 12.2.2. الأدوار (Roles)

يخزن هذا الجدول تعريفات الأدوار الوظيفية المختلفة داخل المؤسسة، مثل مدير مبيعات، محاسب، مدير مخزون.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `role_id`     | `INT (PK)`               | معرف الدور الفريد |
| `role_name`   | `VARCHAR(100)`           | اسم الدور (مثال: مدير مبيعات) |
| `description` | `TEXT`                   | وصف الدور |

### 12.2.3. الصلاحيات (Permissions)

يخزن هذا الجدول الصلاحيات الفردية التي يمكن منحها للمستخدمين أو الأدوار، مثل عرض الفواتير، إنشاء منتج جديد، أو تعديل إعدادات النظام.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `permission_id`| `INT (PK)`               | معرف الصلاحية الفريد |
| `permission_name`| `VARCHAR(100)`           | اسم الصلاحية (مثال: invoices.view, products.create) |
| `description` | `TEXT`                   | وصف الصلاحية |

### 12.2.4. ربط المستخدمين بالأدوار (User-Role Mapping)

يربط هذا الجدول المستخدمين بالأدوار التي ينتمون إليها. يمكن للمستخدم الواحد أن ينتمي إلى دور واحد أو أكثر.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `user_role_id`| `INT (PK)`               | معرف الربط الفريد |
| `user_id`     | `INT (FK)`               | معرف المستخدم |
| `role_id`     | `INT (FK)`               | معرف الدور |

### 12.2.5. ربط الأدوار بالصلاحيات (Role-Permission Mapping)

يربط هذا الجدول الأدوار بالصلاحيات التي يمتلكها كل دور. يتم تحديد الصلاحيات التي يمتلكها المستخدم بناءً على الأدوار التي ينتمي إليها.

| الحقل (Field) | نوع البيانات (Data Type) | الوصف (Description) |
|---------------|--------------------------|---------------------|
| `role_permission_id`| `INT (PK)`               | معرف الربط الفريد |
| `role_id`     | `INT (FK)`               | معرف الدور |
| `permission_id`| `INT (FK)`               | معرف الصلاحية |

## 12.3. المنطق البرمجي الأساسي

يتضمن المنطق البرمجي لموديول المستخدمين والصلاحيات مجموعة من العمليات التي تضمن إدارة آمنة وفعالة للوصول:

### 12.3.1. إنشاء وإدارة حسابات المستخدمين

يتيح النظام للمسؤولين إنشاء حسابات مستخدمين جديدة، وتعيين كلمات مرور، وتحديث معلومات المستخدمين، وتنشيط أو إلغاء تنشيط الحسابات. يجب أن يتضمن النظام آليات قوية لتشفير كلمات المرور (مثل استخدام دوال التجزئة الآمنة) [15].

### 12.3.2. تعريف الأدوار وتخصيص الصلاحيات

يمكن للمسؤولين تعريف أدوار جديدة، وتعيين مجموعة من الصلاحيات لكل دور. يتم تبسيط إدارة الصلاحيات من خلال تعيين الأدوار للمستخدمين بدلاً من تعيين الصلاحيات بشكل فردي لكل مستخدم [15].

### 12.3.3. آلية التحقق من الصلاحيات (Permission Checking)

عند محاولة المستخدم الوصول إلى وظيفة أو بيانات معينة، يقوم النظام بالتحقق من الصلاحيات التي يمتلكها المستخدم (من خلال أدواره) للتأكد من أنه مصرح له بالقيام بهذا الإجراء. يجب أن تكون هذه الآلية فعالة وسريعة لضمان عدم تأثر أداء النظام [15].

## 12.4. واجهات برمجة التطبيقات (APIs)

تُعد APIs لموديول المستخدمين والصلاحيات ضرورية لإدارة المستخدمين والأدوار والصلاحيات برمجياً، ولتمكين الموديولات الأخرى من التحقق من صلاحيات المستخدمين.

*   `POST /users`: لإضافة مستخدم جديد. يتطلب هذا الـ API بيانات المستخدم الأساسية مثل `username`, `email`, `password`, `first_name`, `last_name` [10].
*   `GET /users`: لاستعراض جميع المستخدمين. يمكن أن يدعم فلاتر للبحث حسب اسم المستخدم، البريد الإلكتروني، أو الحالة [10].
*   `GET /users/{id}`: لاستعراض تفاصيل مستخدم محدد باستخدام معرف المستخدم (`user_id`) [10].
*   `PUT /users/{id}`: لتعديل بيانات مستخدم موجود. يتطلب معرف المستخدم (`user_id`) والبيانات المراد تحديثها [10].
*   `DELETE /users/{id}`: لحذف مستخدم. يتطلب معرف المستخدم (`user_id`). يجب أن يتم التحقق من عدم وجود سجلات مرتبطة بالمستخدم قبل الحذف [10].
*   `POST /roles`: لإضافة دور جديد. يتطلب هذا الـ API اسم الدور ووصفه [10].
*   `GET /roles`: لاستعراض جميع الأدوار [10].
*   `PUT /roles/{id}`: لتعديل دور موجود [10].
*   `DELETE /roles/{id}`: لحذف دور [10].
*   `POST /roles/{role_id}/permissions`: لربط صلاحيات بدور معين [10].
*   `GET /permissions`: لاستعراض جميع الصلاحيات المتاحة [10].

## 12.5. التقارير

يوفر موديول المستخدمين والصلاحيات مجموعة من التقارير التي تساعد في مراقبة الوصول والأمان:

*   **قائمة المستخدمين النشطين (Active Users Report):** يُظهر قائمة بجميع المستخدمين النشطين في النظام [6].
*   **تقرير صلاحيات الأدوار (Role Permissions Matrix):** يُوضح الصلاحيات الممنوحة لكل دور، مما يساعد في مراجعة وتدقيق الصلاحيات [6].
*   **تقرير نشاط المستخدمين (User Activity Report):** يُظهر سجلات الأنشطة التي قام بها كل مستخدم، مما يساعد في تتبع الإجراءات والتحقيق في الحوادث الأمنية.

## الخاتمة

لقد استعرض هذا الكتاب البنية التقنية الأساسية لنظام تخطيط موارد المؤسسات (ERP) وموديولاته الرئيسية. من خلال فهم هذه المكونات وتصميمها بعناية، يمكن للمطورين ومهندسي الحلول بناء أنظمة ERP قوية، قابلة للتوسع، وآمنة تلبي احتياجات المؤسسات الحديثة. إن التركيز على البنية المعمارية السليمة، تصميم قواعد البيانات الفعال، واجهات برمجة التطبيقات المرنة، واعتبارات الأمان، سيضمن نجاح أي مشروع لتطوير نظام ERP.

## المراجع (References)

[1] What Is ERP Architecture? Models, Types, and More [2024] - Spinnaker Support. (2024, August 2). Retrieved from https://www.spinnakersupport.com/blog/2024/08/02/erp-architecture/
[2] 8 Core Components of ERP Systems - NetSuite. (2026, April 7). Retrieved from https://www.netsuite.com/portal/resource/articles/erp/erp-systems-components.shtml
[3] ERP System Architecture Explained in Layman\"s Terms - Visual South. (2026, January 20). Retrieved from https://www.visualsouth.com/blog/architecture-of-erp
[4] What Is ERP System Architecture? (Benefits, Types & Differ) - Synconics. Retrieved from https://www.synconics.com/erp-architecture
[5] ERP Fundamentals: How Is ERP Built? Architecture Explained - Resulting IT. (2023, January 24). Retrieved from https://www.resulting-it.com/erp-insights-blog/build-erp-project-integration
[6] ERP System: Modules, Integrated Workings, Landscapes, Master ... - LinkedIn. (2025, October 21). Retrieved from https://www.linkedin.com/pulse/erp-system-modules-integrated-workings-landscapes-master-rahul-sharma-kwgxc
[7] Daftra API: Welcome - Daftra API. Retrieved from https://docs.daftara.dev/
[8] Integration using the Application Programming Interface (API) - Daftra. Retrieved from https://docs.daftara.com/en/tutorial/api/
[9] Api V2 Docs - Daftra. Retrieved from https://azmart.daftra.com/api_docs/v2/
[10] Endpoints Structure - Daftra API. Retrieved from https://docs.daftara.dev/1259001m0
[11] API - Daftra Knowledge Base. Retrieved from https://docs.daftara.com/en/category/developers/api-en/
[12] How to Conduct an Effective Inventory Audit: Best Practices - VersaCloud ERP. (2024, October 28). Retrieved from https://www.versaclouderp.com/blog/how-to-conduct-an-effective-inventory-audit-best-practices/
[13] A Guide to ERP Software for Financial Systems | RubinBrown. (2025, January 24). Retrieved from https://www.rubinbrown.com/insights-events/insight-articles/essential-erp-features-for-an-effective-financial-management-system/
[14] A Guide to Inventory Audits: Meaning, Types & Best Practices - QuickDice ERP. (2025, November 8). Retrieved from https://quickdiceerp.com/blog/a-guide-to-inventory-audits-meaning-types-best-practices
[15] ERP Implementation: The 9-Step Guide – Forbes Advisor. (2024, July 9). Retrieved from https://www.forbes.com/advisor/business/erp-implementation/
